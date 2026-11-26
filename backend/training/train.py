"""Offline, reproducible training of the SoundPass taste model.

Run (never at user registration time):

    docker run --rm -v "${PWD}/backend:/work" -w /work python:3.13-slim sh -c \
      "pip install -q -r training/requirements-train.txt && python -m training.train"

Method adapted from https://github.com/imaakro/soundpass-recomendador-kmeans
(MIT License, Copyright (c) 2026 Camilo Montenegro, Esteban Parra; notice in NOTICE-MIT.md):
four musical signals, optional PCA to two components, K-means. Differences: curated artist
profiles instead of Spotify tracks, a by-artist train/evaluation split, a comparison of
standardised 4-D versus standardised+PCA, k=2..8 and ten seeds, and JSON artifacts instead
of pickles. Only artist_profiles.json (project-authored, see its provenance) is read.
"""

import hashlib
import json
import math
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT.parent
sys.path.insert(0, str(BACKEND))

from src.recommendation import engine  # noqa: E402  (same code as the runtime ranks the evaluation)

PROFILES = ROOT / "artist_profiles.json"
PERSONAS = ROOT / "taste_profiles.json"
OUT_DIR = BACKEND / "src" / "recommendation" / "artifacts"
REPORT = ROOT / "metrics_report.json"

SEEDS = tuple(range(10))
K_RANGE = tuple(range(2, 9))
EVAL_FRACTION = 0.25
MIN_ARTISTS = 12
WEIGHTS = {"scales": 0.4, "artists": 0.4, "genres": 0.2}
FALLBACK_PENALTY = 0.35
MIN_STABILITY = 0.8
MIN_K = 3
SPLIT_SALT = "soundpass-split-v1"
CONFIGS = ("scaled_4d", "scaled_pca2")


class TrainingError(ValueError):
    pass


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def dump(value):
    def clean(x):
        if isinstance(x, float):
            return round(x, 10)
        if isinstance(x, dict):
            return {k: clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [clean(v) for v in x]
        return x
    return (json.dumps(clean(value), ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")


def split_by_artist(artists, fraction=EVAL_FRACTION):
    """Deterministic split by artist ID, stratified by primary genre: no artist is in both sets."""
    groups = {}
    for artist in artists:
        groups.setdefault(artist["genres"][0], []).append(artist)
    train, held_out = [], []
    for genre in sorted(groups):
        rows = sorted(groups[genre], key=lambda a: sha256_bytes(f"{SPLIT_SALT}:{a['id']}".encode()))
        n_eval = int(len(rows) * fraction) if len(rows) >= 4 else 0
        held_out += rows[:n_eval]
        train += rows[n_eval:]
    return sorted(train, key=lambda a: a["id"]), sorted(held_out, key=lambda a: a["id"])


def fit_preprocessing(np, X, pca):
    from sklearn.decomposition import PCA
    mean = X.mean(axis=0)
    scale = X.std(axis=0)
    scale[scale == 0] = 1.0
    pre = {"mean": mean, "scale": scale, "pca": None}
    if pca:
        model = PCA(n_components=2, svd_solver="full").fit((X - mean) / scale)
        pre["pca"] = {"mean": model.mean_, "components": model.components_}
    return pre


def apply_preprocessing(pre, X):
    Z = (X - pre["mean"]) / pre["scale"]
    if pre["pca"] is not None:
        Z = (Z - pre["pca"]["mean"]) @ pre["pca"]["components"].T
    return Z


def fit_kmeans(Z, k, seed):
    from sklearn.cluster import KMeans
    return KMeans(n_clusters=k, n_init=10, random_state=seed).fit(Z)


def silhouette(Z, labels):
    from sklearn.metrics import silhouette_score
    n_labels = len(set(labels))
    if n_labels < 2 or n_labels > len(labels) - 1:
        return None
    return float(silhouette_score(Z, labels))


def compare_configs(np, train_X, eval_X, k_range=K_RANGE, seeds=SEEDS):
    from sklearn.metrics import adjusted_rand_score as ari
    rows = []
    for config in CONFIGS:
        pre = fit_preprocessing(np, train_X, config == "scaled_pca2")
        Z, Ze = apply_preprocessing(pre, train_X), (apply_preprocessing(pre, eval_X) if len(eval_X) else None)
        for k in k_range:
            fits = [fit_kmeans(Z, k, seed) for seed in seeds]
            best = min(fits, key=lambda f: (round(f.inertia_, 9), 0))
            labels = [f.labels_ for f in fits]
            pairs = [ari(a, b) for a, b in combinations(labels, 2)]
            subsample = []
            for seed in seeds:
                rng = np.random.RandomState(seed)
                idx = rng.choice(len(Z), size=max(k + 1, int(len(Z) * 0.8)), replace=False)
                sub = fit_kmeans(Z[idx], k, 0)
                subsample.append(ari(best.labels_, sub.predict(Z)))
            eval_labels = best.predict(Ze) if Ze is not None else None
            sizes = sorted(int((best.labels_ == c).sum()) for c in range(k))
            rows.append({
                "config": config, "k": k,
                "silhouette_train_mean_seeds": float(np.mean([silhouette(Z, l) for l in labels])),
                "silhouette_train": silhouette(Z, best.labels_),
                "silhouette_eval": silhouette(Ze, eval_labels) if Ze is not None else None,
                "stability_ari_seeds": float(np.mean(pairs)),
                "stability_ari_subsample": float(np.mean(subsample)),
                "min_cluster_size": sizes[0], "cluster_sizes": sizes,
            })
    return rows


def score(row):
    """Mean of train and held-out silhouette (train only when there is no held-out set)."""
    values = [v for v in (row["silhouette_train"], row["silhouette_eval"]) if v is not None]
    return sum(values) / len(values)


def select(rows, n_train):
    """Highest mean(train, held-out) silhouette among stable, non-degenerate fits; ties prefer 4-D, then smaller k."""
    floor = max(3, math.ceil(0.05 * n_train))
    # Product rule: k=2 only splits off ~20% of artists, too coarse to gate recommendations.
    allowed = [r for r in rows if r["k"] >= MIN_K] or rows
    ok = [r for r in allowed if r["silhouette_train"] is not None and r["min_cluster_size"] >= floor
          and min(r["stability_ari_seeds"], r["stability_ari_subsample"]) >= MIN_STABILITY]
    pool = ok or [r for r in allowed if r["silhouette_train"] is not None]
    if not pool:
        raise TrainingError("no hay ajuste valido")
    best = min(pool, key=lambda r: (-round(score(r), 6), CONFIGS.index(r["config"]), r["k"]))
    return best, bool(ok)


def cluster_description(mean):
    d, e, a, v = mean
    tags = []
    if d >= 0.7: tags.append("Bailable")
    if e >= 0.75: tags.append("Enérgico")
    elif e <= 0.45: tags.append("Tranquilo")
    if a >= 0.5: tags.append("Acústico")
    if v >= 0.65: tags.append("Alegre")
    elif v <= 0.4: tags.append("Melancólico")
    name = " y ".join(tags[:2]) if tags else "Equilibrado"
    return name, (f"Bailable {d:.2f} · energía {e:.2f} · acústico {a:.2f} · ánimo {v:.2f} (promedio del grupo)")


def build_artifact(np, doc, profiles_sha, train, held_out, config, k, seed=None):
    train_X = np.array([a["vector"] for a in train], dtype=float)
    pre = fit_preprocessing(np, train_X, config == "scaled_pca2")
    Z = apply_preprocessing(pre, train_X)
    if seed is None:
        fits = {s: fit_kmeans(Z, k, s) for s in SEEDS}
        seed = min(SEEDS, key=lambda s: (round(fits[s].inertia_, 9), s))
        km = fits[seed]
    else:
        km = fit_kmeans(Z, k, seed)
    raw_means = [train_X[km.labels_ == c].mean(axis=0) for c in range(k)]
    order = sorted(range(k), key=lambda c: (round(raw_means[c][1], 9), round(raw_means[c][0], 9), c))
    centroids = [km.cluster_centers_[c] for c in order]
    clusters, seen = [], {}
    for new, old in enumerate(order):
        name, description = cluster_description(raw_means[old])
        seen[name] = seen.get(name, 0) + 1
        clusters.append({"id": new, "name": name if seen[name] == 1 else f"{name} ({seen[name]})",
                         "description": description, "size": int((km.labels_ == old).sum())})
    protos = {}
    by_genre = {}
    for a in train:
        by_genre.setdefault(a["genres"][0], []).append(a["vector"])
    for genre, vectors in sorted(by_genre.items()):
        if len(vectors) >= 3:
            protos[genre] = np.mean(np.array(vectors), axis=0)
    artifact = {
        "schema": 1, "features": list(engine.FEATURES),
        "version": f"kmeans-{config}-k{k}-{profiles_sha[:8]}",
        "profiles_sha256": profiles_sha,
        "preprocessing": {"mean": pre["mean"], "scale": pre["scale"],
                          "pca": pre["pca"] and {"mean": pre["pca"]["mean"], "components": pre["pca"]["components"]}},
        "centroids": centroids, "clusters": clusters,
        "genre_prototypes": protos, "weights": WEIGHTS, "fallback_penalty": FALLBACK_PENALTY,
        "training": {"config": config, "k": k, "seed": seed, "train_artists": len(train),
                     "eval_artists": len(held_out), "split": f"{SPLIT_SALT}, stratified by primary genre",
                     "seeds_compared": list(SEEDS)},
    }
    artifact = json.loads(dump(_listify(artifact)))
    model = engine.Model(artifact)
    sample = [a["vector"] for a in train[:5]]
    artifact["self_check"] = []
    for vec in sample:
        cluster, point = model.assign(vec)
        artifact["self_check"].append({"input": vec, "cluster": cluster, "point": list(point)})
    return json.loads(dump(artifact))


def _listify(x):
    if hasattr(x, "tolist"):
        return x.tolist()
    if isinstance(x, dict):
        return {k: _listify(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_listify(v) for v in x]
    return x


def evaluate_top5(artifact, doc, personas, train, held_out):
    model, store = engine.Model(artifact), engine.ProfileStore(doc)
    from datetime import date
    today = date(2099, 1, 1)
    train_ids = {a["id"] for a in train}
    events = [{"id": a["id"], "artist": a["name"], "artist_id": None, "event_date": "2099-06-01", "genre": ""}
              for a in held_out]
    primary = {a["name"]: a["genres"][0] for a in held_out}
    results, base = [], {"kmeans_then_distance": [], "distance_only": [], "genre_only": [], "random_expected": []}
    for p in personas:
        favorites = [a["id"] for a in train if a["name"] in p["favorites"]]
        vec = engine.user_vector(model, store, p["genres"], favorites, p["scales"])
        relevant = {a["name"] for a in held_out if a["genres"][0] in p["expected_genres"]}
        _, top = engine.rank(model, store, vec, events, today, limit=5)
        point = model.project(vec)
        by_distance = sorted(held_out, key=lambda a: (round(engine._distance(model.project(a["vector"]), point), 9), a["id"]))[:5]
        by_genre = [a for a in sorted(held_out, key=lambda a: a["id"]) if a["genres"][0] in p["genres"]][:5]
        hit = lambda names: sum(n in relevant for n in names) / 5
        row = {"persona": p["id"], "relevant_in_eval": len(relevant),
               "top5": [t["artist"] for t in top],
               "precision_at_5": hit([t["artist"] for t in top])}
        results.append(row)
        base["kmeans_then_distance"].append(row["precision_at_5"])
        base["distance_only"].append(hit([a["name"] for a in by_distance]))
        base["genre_only"].append(hit([a["name"] for a in by_genre]))
        base["random_expected"].append(len(relevant) / max(1, len(held_out)))
    mean = lambda xs: sum(xs) / len(xs) if xs else None
    return {"personas": results, "mean_precision_at_5": {k: mean(v) for k, v in base.items()},
            "personas_with_all_top5_relevant": sum(r["precision_at_5"] == 1.0 for r in results),
            "persona_count": len(results)}


def catalog_coverage(artifact, doc, snapshot):
    model, store = engine.Model(artifact), engine.ProfileStore(doc)
    counts = {"profile_vector": 0, "genre_fallback": 0, "none": 0}
    rows = []
    for artist_id, name, genre in snapshot["artists"]:
        profile = store.lookup(artist_id, name)
        if profile and profile.vector:
            kind = "profile_vector"
        elif model.genre_prototypes.get(engine.PROVIDER_GENRES.get(engine.normalize_name(genre), "")):
            kind = "genre_fallback"
        else:
            kind = "none"
        counts[kind] += 1
        rows.append({"artist": name, "signal": kind})
    total = max(1, len(rows))
    return {"artists": len(rows), **counts, "coverage": (total - counts["none"]) / total,
            "with_own_vector": counts["profile_vector"] / total, "detail": rows}


def run(write=True):
    import numpy as np
    import sklearn
    raw = PROFILES.read_bytes()
    profiles_sha = sha256_bytes(raw)
    doc = json.loads(raw)
    personas = json.loads(PERSONAS.read_text(encoding="utf-8"))
    artists = [a for a in doc["artists"] if a["vector"] is not None]
    if len(artists) < MIN_ARTISTS:
        raise TrainingError(f"se necesitan al menos {MIN_ARTISTS} artistas con vector (hay {len(artists)})")
    train, held_out = split_by_artist(artists)
    k_range = tuple(k for k in K_RANGE if k <= len(train) // 3)
    if not k_range:
        raise TrainingError("conjunto de entrenamiento demasiado pequeno para k>=2")
    train_X = np.array([a["vector"] for a in train], dtype=float)
    eval_X = np.array([a["vector"] for a in held_out], dtype=float).reshape(-1, 4)
    rows = compare_configs(np, train_X, eval_X, k_range)
    chosen, gate = select(rows, len(train))
    artifact = build_artifact(np, doc, profiles_sha, train, held_out, chosen["config"], chosen["k"])
    per_config = {}
    for config in CONFIGS:
        best = min((r for r in rows if r["config"] == config and r["silhouette_train"] is not None),
                   key=lambda r: (-round(r["silhouette_train"], 6), r["k"]), default=None)
        if best:
            candidate = build_artifact(np, doc, profiles_sha, train, held_out, config, best["k"])
            per_config[config] = {"k": best["k"], "top5": evaluate_top5(candidate, doc, personas["personas"], train, held_out)}
    chosen_top5 = evaluate_top5(artifact, doc, personas["personas"], train, held_out)
    coverage = catalog_coverage(artifact, doc, personas["catalog_snapshot"])
    report = {
        "profiles_sha256": profiles_sha, "library_versions": {"numpy": np.__version__, "scikit-learn": sklearn.__version__},
        "artists_total": len(doc["artists"]), "artists_with_vector": len(artists),
        "artists_without_vector": len(doc["artists"]) - len(artists),
        "train_artists": len(train), "eval_artists": len(held_out),
        "selection_rule": ("max promedio de silueta (entrenamiento y evaluacion) entre ajustes con k >= 3, estabilidad ARI (semillas y submuestras) >= "
                           f"{MIN_STABILITY} y grupo minimo >= max(3, 5% del entrenamiento); empate: 4-D, k menor"),
        "quality_gate_passed": gate, "chosen": chosen, "comparison": rows,
        "reference_repo_metrics": {"k": 3, "silhouette": 0.423, "note": "otro dataset (Spotify) y otra base; no comparable directamente"},
        "top5_selected": chosen_top5, "top5_by_config_best_k": per_config, "catalog_coverage": coverage,
    }
    artifact["metrics"] = {
        "silhouette_train": chosen["silhouette_train"], "silhouette_eval": chosen["silhouette_eval"],
        "stability_ari_seeds": chosen["stability_ari_seeds"],
        "stability_ari_subsample": chosen["stability_ari_subsample"],
        "mean_precision_at_5": chosen_top5["mean_precision_at_5"], "catalog_coverage": coverage["coverage"],
        "quality_gate_passed": gate,
    }
    artifact = json.loads(dump(artifact))
    if write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        model_bytes = dump(artifact)
        (OUT_DIR / "model.json").write_bytes(model_bytes)
        (OUT_DIR / "artist_profiles.json").write_bytes(raw)
        (OUT_DIR / "manifest.json").write_bytes(dump({
            "schema": 1, "files": {"model.json": sha256_bytes(model_bytes), "artist_profiles.json": profiles_sha}}))
        REPORT.write_bytes(dump(report))
    return artifact, report


if __name__ == "__main__":
    model_artifact, summary = run()
    print(json.dumps({"chosen": summary["chosen"], "gate": summary["quality_gate_passed"],
                      "top5": summary["top5_selected"]["mean_precision_at_5"],
                      "coverage": summary["catalog_coverage"]["coverage"]}, indent=1, default=str))
