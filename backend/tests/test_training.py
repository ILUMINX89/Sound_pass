"""Training checks. Need numpy and scikit-learn, so they run only in the training container:

    docker run --rm -v "${PWD}/backend:/work" -w /work python:3.13-slim sh -c \
      "pip install -q -r training/requirements-train.txt && python tests/test_training.py"
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import numpy  # noqa: F401
    import sklearn  # noqa: F401
    from training import train
except ImportError:  # pragma: no cover
    train = None


@unittest.skipUnless(train, "requiere numpy y scikit-learn")
class TrainingTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(train.PROFILES.read_text(encoding="utf-8"))
        self.artists = [a for a in self.doc["artists"] if a["vector"] is not None]

    def test_split_is_by_artist_deterministic_and_leak_free(self):
        a_train, a_eval = train.split_by_artist(self.artists)
        again = train.split_by_artist(list(reversed(self.artists)))
        self.assertEqual(([a["id"] for a in a_train], [a["id"] for a in a_eval]),
                         ([a["id"] for a in again[0]], [a["id"] for a in again[1]]))
        self.assertFalse({a["id"] for a in a_train} & {a["id"] for a in a_eval})
        self.assertEqual(len(a_train) + len(a_eval), len(self.artists))
        self.assertTrue(a_eval)

    def test_artists_without_vector_never_train(self):
        a_train, a_eval = train.split_by_artist(self.artists)
        missing = {a["id"] for a in self.doc["artists"] if a["vector"] is None}
        self.assertTrue(missing)
        self.assertFalse(missing & {a["id"] for a in a_train + a_eval})

    def test_small_dataset_is_refused(self):
        small = {**self.doc, "artists": self.doc["artists"][:5]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "small.json"
            path.write_text(json.dumps(small), encoding="utf-8")
            original = train.PROFILES
            train.PROFILES = path
            try:
                with self.assertRaises(train.TrainingError):
                    train.run(write=False)
            finally:
                train.PROFILES = original

    def test_borderline_dataset_trains_with_fewer_clusters(self):
        small = {**self.doc, "artists": self.artists[:30]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "small.json"
            path.write_text(json.dumps(small), encoding="utf-8")
            original = train.PROFILES
            train.PROFILES = path
            try:
                artifact, report = train.run(write=False)
            finally:
                train.PROFILES = original
        self.assertLessEqual(max(r["k"] for r in report["comparison"]), len(report["comparison"]) and 8)
        self.assertLessEqual(len(artifact["centroids"]), report["train_artists"] // 3)

    def test_training_is_reproducible_and_matches_shipped_artifacts(self):
        first, _ = train.run(write=False)
        second, _ = train.run(write=False)
        self.assertEqual(train.dump(first), train.dump(second))
        shipped = (train.OUT_DIR / "model.json").read_bytes()
        self.assertEqual(train.dump(first), shipped)

    def test_selection_prefers_generalisation_and_rejects_unstable(self):
        base = {"config": "scaled_4d", "silhouette_eval": 0.3, "stability_ari_seeds": 1.0,
                "stability_ari_subsample": 1.0, "min_cluster_size": 10}
        rows = [
            {**base, "k": 2, "silhouette_train": 0.9},                                    # below MIN_K
            {**base, "k": 3, "silhouette_train": 0.5, "silhouette_eval": 0.1},            # weak held-out
            {**base, "k": 4, "silhouette_train": 0.4, "silhouette_eval": 0.45},           # chosen
            {**base, "k": 5, "silhouette_train": 0.8, "stability_ari_subsample": 0.5},    # unstable
        ]
        best, gate = train.select(rows, 100)
        self.assertEqual((best["k"], gate), (4, True))


if __name__ == "__main__":
    unittest.main()
