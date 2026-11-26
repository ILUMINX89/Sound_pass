"""Pure-Python K-means recommender runtime (no training, no heavy dependencies).

Adapted from https://github.com/imaakro/soundpass-recomendador-kmeans (MIT License,
Copyright (c) 2026 Camilo Montenegro, Esteban Parra; see backend/training/NOTICE-MIT.md).
Reused ideas: four musical signals (danceability, energy, acousticness, valence), slider
values mapped to a taste vector, projection into the space where K-means was trained,
cluster assignment, and ordering "same profile first, then distance" (src/predict.py).
Nothing is trained here: centroids and preprocessing come from a versioned artifact.
"""

import math
import re
from dataclasses import dataclass
from datetime import date, timedelta
from unicodedata import normalize

FEATURES = ("danceability", "energy", "acousticness", "valence")
SCALE_FIELDS = ("danceability", "energy", "acousticness", "mood")
SCALE_MIN, SCALE_MAX = 1, 5

# Provider genre labels (Ticketmaster) -> curated genre ids.
PROVIDER_GENRES = {
    "latin": "latin", "hip-hop/rap": "hip_hop", "pop": "pop", "rock": "rock", "hard rock": "rock",
    "alternative": "alternative", "alternative rock": "alternative", "folk": "folk",
    "dance/electronic": "electronic", "electronic": "electronic", "r&b": "rnb", "country": "country",
    "jazz": "jazz_blues", "blues": "jazz_blues", "world": "world", "metal": "metal", "reggae": "reggae",
}
INACTIVE = {"canceled", "cancelled", "postponed", "rescheduled", "inactive", "aplazado", "cancelado"}
ADD_ON = re.compile(
    r"\b(vip|suites?|parking|estacionamiento|premium seats?|hospitality|meet[ -]and[ -]greet|"
    r"add[ -]ons?|upgrades?|cannot split by day|2[ -]day tickets?)\b", re.IGNORECASE)


class ArtifactError(ValueError):
    pass


def normalize_name(value):
    return " ".join(normalize("NFKC", value or "").casefold().split())


def _vector(value, size, what):
    if (not isinstance(value, list) or len(value) != size
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in value)):
        raise ArtifactError(f"{what} invalido")
    return tuple(float(x) for x in value)


def _distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


@dataclass(frozen=True)
class Artist:
    id: str
    name: str
    genres: tuple
    vector: tuple | None
    ticketmaster_ids: tuple
    aliases: tuple = ()


class ProfileStore:
    """Curated artist profiles with stable IDs."""

    def __init__(self, document):
        try:
            self.genres = dict(document["genres"])
            artists = [self._artist(row) for row in document["artists"]]
        except (KeyError, TypeError) as error:
            raise ArtifactError("perfiles invalidos") from error
        self.by_id = {a.id: a for a in artists}
        if len(self.by_id) != len(artists):
            raise ArtifactError("IDs de artista duplicados")
        self.by_tm, self.by_name = {}, {}
        for artist in artists:
            for tm_id in artist.ticketmaster_ids:
                if self.by_tm.setdefault(tm_id, artist) is not artist:
                    raise ArtifactError("ID de Ticketmaster duplicado")
            for name in (artist.name, *artist.aliases):
                self.by_name.setdefault(normalize_name(name), []).append(artist)

    @staticmethod
    def _artist(row):
        vector = row.get("vector")
        if vector is not None:
            vector = _vector(vector, 4, "vector de artista")
            if any(not 0 <= x <= 1 for x in vector):
                raise ArtifactError("vector fuera de rango")
        ids = tuple(str(x) for x in row.get("ticketmaster_ids") or [])
        return Artist(str(row["id"]), str(row["name"]), tuple(row["genres"]), vector, ids,
                      tuple(row.get("aliases") or ()))

    def lookup(self, artist_id, name, ambiguous_name=False):
        """Provider ID first; a name only when it is unique in the catalog and in the profiles."""
        if artist_id is not None and str(artist_id) in self.by_tm:
            return self.by_tm[str(artist_id)]
        matches = self.by_name.get(normalize_name(name), [])
        return matches[0] if len(matches) == 1 and not ambiguous_name else None


class Model:
    def __init__(self, data):
        try:
            if data["schema"] != 1 or tuple(data["features"]) != FEATURES:
                raise ArtifactError("esquema no compatible")
            self.version = str(data["version"])
            self.profiles_sha256 = str(data["profiles_sha256"])
            pre = data["preprocessing"]
            self.mean = _vector(pre["mean"], 4, "media")
            self.scale = _vector(pre["scale"], 4, "escala")
            if any(s <= 0 for s in self.scale):
                raise ArtifactError("escala invalida")
            pca = pre.get("pca")
            self.pca_mean = self.components = None
            if pca:
                self.pca_mean = _vector(pca["mean"], 4, "media PCA")
                comps = pca["components"]
                if not isinstance(comps, list) or not comps:
                    raise ArtifactError("componentes invalidos")
                self.components = tuple(_vector(row, 4, "componente") for row in comps)
            dim = len(self.components) if self.components else 4
            self.centroids = tuple(_vector(row, dim, "centroide") for row in data["centroids"])
            self.clusters = list(data["clusters"])
            if not self.centroids or len(self.clusters) != len(self.centroids):
                raise ArtifactError("centroides invalidos")
            self.genre_prototypes = {str(k): _vector(v, 4, "prototipo") for k, v in data["genre_prototypes"].items()}
            weights = data["weights"]
            self.weights = {k: float(weights[k]) for k in ("scales", "artists", "genres")}
            self.fallback_penalty = float(data["fallback_penalty"])
            if any(not math.isfinite(w) or w <= 0 for w in self.weights.values()):
                raise ArtifactError("pesos invalidos")
            if not math.isfinite(self.fallback_penalty) or self.fallback_penalty < 0:
                raise ArtifactError("penalizacion invalida")
            self.metrics = data.get("metrics", {})
            self.self_check = data.get("self_check", [])
        except (KeyError, TypeError, AttributeError) as error:
            raise ArtifactError("modelo invalido") from error

    def project(self, vector):
        z = [(x - m) / s for x, m, s in zip(vector, self.mean, self.scale)]
        if self.components is None:
            return tuple(z)
        centered = [x - m for x, m in zip(z, self.pca_mean)]
        return tuple(sum(c * x for c, x in zip(row, centered)) for row in self.components)

    def assign(self, vector):
        """Cluster index of a raw 4-signal vector, and the projected point."""
        point = self.project(vector)
        distances = [_distance(point, c) for c in self.centroids]
        return min(range(len(distances)), key=lambda i: (round(distances[i], 12), i)), point

    def verify(self):
        for row in self.self_check:
            cluster, point = self.assign(row["input"])
            if cluster != row["cluster"] or _distance(point, row["point"]) > 1e-6:
                raise ArtifactError("autoverificacion del modelo fallida")


def user_vector(model, store, genres=(), artist_ids=(), scales=None):
    """Combine the three questionnaire signals into one raw 4-signal vector.

    scales: 1-5 answers mapped to 0-1 (weight 0.4). Artists: mean of their profile vectors,
    or of their curated genre prototype when the vector is missing (weight 0.4). Genres: mean
    of genre prototypes (weight 0.2). Weights are renormalised over the signals present.
    """
    parts = []
    if scales:
        parts.append((model.weights["scales"], [(s - SCALE_MIN) / (SCALE_MAX - SCALE_MIN) for s in scales]))
    vectors = []
    for artist_id in artist_ids:
        artist = store.by_id.get(artist_id)
        vector = artist.vector if artist else None
        if vector is None and artist:
            vector = next((model.genre_prototypes[g] for g in artist.genres if g in model.genre_prototypes), None)
        if vector is not None:
            vectors.append(vector)
    if vectors:
        parts.append((model.weights["artists"], _mean(vectors)))
    protos = [model.genre_prototypes[g] for g in genres if g in model.genre_prototypes]
    if protos:
        parts.append((model.weights["genres"], _mean(protos)))
    if not parts:
        return None
    total = sum(w for w, _ in parts)
    return tuple(sum(w * v[i] for w, v in parts) / total for i in range(4))


def _mean(vectors):
    return [sum(v[i] for v in vectors) / len(vectors) for i in range(4)]


def _eligible(event, today):
    try:
        day = date.fromisoformat(str(event.get("event_date")))
    except ValueError:
        return False
    return (day >= today - timedelta(days=1)
            and str(event.get("status") or "").lower() not in INACTIVE
            and not ADD_ON.search(str(event.get("tour_name") or event.get("name") or "")))


def rank(model, store, vector, events, today, limit=12):
    """Artists with future eligible events, nearest to the user's taste first.

    Same cluster as the user first, then Euclidean distance in the model space; ties are broken
    by the artist key so the order is deterministic. Genre-only candidates carry a fixed penalty.
    """
    cluster, user_point = model.assign(vector)
    groups, names = {}, {}
    for event in events:
        if not _eligible(event, today):
            continue
        artist_id = event.get("artist_id")
        name = normalize_name(event.get("artist"))
        if artist_id:
            names.setdefault(name, set()).add(str(artist_id))
        key = f"id:{artist_id}" if artist_id else f"name:{name}"
        group = groups.setdefault(key, {"event": event, "artist_id": artist_id, "name": name})
        if (event["event_date"], str(event.get("id"))) < (group["event"]["event_date"], str(group["event"].get("id"))):
            group["event"] = event
    ranked = []
    for key, group in groups.items():
        event = group["event"]
        profile = store.lookup(group["artist_id"], group["name"], len(names.get(group["name"], ())) > 1)
        penalty, source = 0.0, "profile"
        vec = profile.vector if profile else None
        if vec is None:
            genre = next((g for g in profile.genres if g in model.genre_prototypes), None) if profile else None
            genre = genre or PROVIDER_GENRES.get(normalize_name(event.get("genre")))
            vec = model.genre_prototypes.get(genre) if genre else None
            penalty, source = model.fallback_penalty, "genre"
        if vec is None:
            continue
        candidate_cluster, point = model.assign(vec)
        distance = _distance(point, user_point) + penalty
        ranked.append(((candidate_cluster != cluster, round(distance, 9), key), {
            "artist_id": None if group["artist_id"] is None else str(group["artist_id"]),
            "artist": event.get("artist"),
            "profile_id": profile.id if profile else None,
            "source": source,
            "same_profile": candidate_cluster == cluster,
            "distance": round(distance, 4),
            "event_id": str(event.get("id")),
            "event_date": event["event_date"],
        }))
    ranked.sort(key=lambda row: row[0])
    return cluster, [row[1] for row in ranked[:limit]]
