"""Pruebas aisladas del recomendador: sin red, sin la BD configurada y sin entrenar."""
import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src import models
from src.database import Base, get_db
from src.main import app
from src.recommendation import engine, loader
from src.routers import preferences

FOLK = {"genres": ["folk"], "artist_ids": ["art_jose_gonzalez"],
        "scales": {"danceability": 2, "energy": 1, "acousticness": 5, "mood": 2}}
URBAN = {"genres": ["latin", "hip_hop"], "artist_ids": ["art_bad_bunny"],
         "scales": {"danceability": 5, "energy": 4, "acousticness": 1, "mood": 4}}
FUTURE = "2099-06-01"


def card(event_id, name, artist_id, genre, event_date=FUTURE, status="onsale", tour=None):
    return {"id": event_id, "source": "ticketmaster", "artist": name, "artist_id": artist_id,
            "event_date": event_date, "event_time": "20:00:00", "genre": genre, "status": status,
            "tour_name": tour or name, "venue": {"name": "Sala", "city": "Bogotá"}}


CATALOG = [
    card("e1", "Bob Dylan", "K8vZ9171ueV", "Rock", "2099-07-01"),
    card("e1b", "Bob Dylan", "K8vZ9171ueV", "Rock", "2099-06-02"),
    card("e2", "José González", "K8vZ9175Yn7", "Folk"),
    card("e3", "Chris de Burgh", "K8vZ9175pnV", "Rock"),
    card("e4", "Don Omar", "K8vZ9175yK0", "Latin"),
    card("e5", "Karol G", "K8vZ917p3-V", "Latin"),
    card("e6", "Paulo Londra", "K8vZ917bAfV", "Hip-Hop/Rap"),
    card("e7", "Lila Downs", "K8vZ9171sw0", "World"),
    card("e8", "Camilo", "K8vZ917_FzV", "Latin"),
]


class ApiTests(unittest.TestCase):
    def setUp(self):
        loader.get_service.cache_clear()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        def test_db():
            yield self.db
        app.dependency_overrides[get_db] = test_db
        self.client = TestClient(app)
        self.events = list(CATALOG)
        patches = [patch.object(preferences, "get_public_concerts", lambda q, c: list(self.events)),
                   patch.object(preferences, "artist_catalog", lambda db: {})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); self.db.close(); self.engine.dispose()

    def signup(self, name):
        data = {"full_name": name, "email": f"{name}@example.com", "password": "Password123!"}
        self.assertEqual(self.client.post("/auth/register", json=data).status_code, 201)
        token = self.client.post("/auth/login", json=data).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, data

    def recs(self, headers):
        response = self.client.get("/preferences/me/recommendations", headers=headers)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_new_account_has_no_answers_and_general_catalog(self):
        headers, _ = self.signup("nueva")
        self.assertEqual(self.client.get("/preferences/me", headers=headers).json()["status"], "unset")
        body = self.recs(headers)
        self.assertEqual((body["available"], body["reason"], body["items"]), (False, "no_preferences", []))

    def test_opposite_tastes_edit_and_relogin(self):
        a, creds = self.signup("folk")
        b, _ = self.signup("urbano")
        self.assertEqual(self.client.put("/preferences/me", json=FOLK, headers=a).status_code, 200)
        self.assertEqual(self.client.put("/preferences/me", json=URBAN, headers=b).status_code, 200)
        ra, rb = self.recs(a), self.recs(b)
        names_a, names_b = [i["artist"] for i in ra["items"]], [i["artist"] for i in rb["items"]]
        self.assertTrue(ra["available"] and rb["available"])
        self.assertIn(names_a[0], {"José González", "Bob Dylan", "Chris de Burgh"})
        self.assertIn(names_b[0], {"Don Omar", "Karol G", "Paulo Londra"})
        self.assertNotEqual(names_a, names_b)
        self.assertEqual(len(names_a), len(set(names_a)), "una tarjeta por artista")
        dylan = next(i for i in ra["items"] if i["artist"] == "Bob Dylan")
        self.assertEqual((dylan["event_id"], dylan["event_date"]), ("e1b", "2099-06-02"), "fecha valida mas cercana")
        # editing produces a different ranking
        self.assertEqual(self.client.put("/preferences/me", json=URBAN, headers=a).status_code, 200)
        self.assertNotEqual([i["artist"] for i in self.recs(a)["items"]], names_a)
        self.assertEqual([i["artist"] for i in self.recs(a)["items"]], names_b)
        # a fresh login recovers the saved answers
        token = self.client.post("/auth/login", json=creds).json()["access_token"]
        again = {"Authorization": f"Bearer {token}"}
        saved = self.client.get("/preferences/me", headers=again).json()
        self.assertEqual((saved["status"], saved["genres"], saved["artist_ids"], saved["scales"]),
                         ("answered", URBAN["genres"], URBAN["artist_ids"], URBAN["scales"]))
        self.assertEqual([i["artist"] for i in self.recs(again)["items"]], names_b)

    def test_skip_is_persisted_and_never_erases_answers(self):
        a, _ = self.signup("omite")
        self.assertEqual(self.client.post("/preferences/me/skip", headers=a).json()["status"], "skipped")
        self.assertEqual(self.recs(a)["reason"], "no_preferences")
        self.client.put("/preferences/me", json=FOLK, headers=a)
        self.assertEqual(self.client.post("/preferences/me/skip", headers=a).json()["status"], "answered")
        self.assertTrue(self.recs(a)["available"])

    def test_isolation_between_accounts(self):
        a, _ = self.signup("a")
        b, _ = self.signup("b")
        self.client.put("/preferences/me", json=FOLK, headers=a)
        self.assertEqual(self.client.get("/preferences/me", headers=b).json()["status"], "unset")
        self.client.put("/preferences/me", json=URBAN, headers=b)
        self.assertEqual(self.client.get("/preferences/me", headers=a).json()["genres"], FOLK["genres"])
        self.assertEqual(self.db.query(models.UserPreference).count(), 2)
        # no user identifier is accepted anywhere
        self.assertEqual(self.client.put("/preferences/me", json={**FOLK, "user_id": 2}, headers=a).status_code, 422)
        self.assertEqual(self.client.get("/preferences/2", headers=a).status_code, 404)
        for method, path in (("get", "/preferences/me"), ("put", "/preferences/me"),
                             ("post", "/preferences/me/skip"), ("get", "/preferences/me/recommendations")):
            response = getattr(self.client, method)(path, **({"json": FOLK} if method == "put" else {}))
            self.assertEqual(response.status_code, 401, path)
        bad = {"Authorization": "Bearer not-a-token"}
        self.assertEqual(self.client.get("/preferences/me", headers=bad).status_code, 401)

    def test_backend_validation(self):
        a, _ = self.signup("valida")
        scales = FOLK["scales"]
        invalid = [
            {**FOLK, "scales": {**scales, "energy": 0}}, {**FOLK, "scales": {**scales, "energy": 6}},
            {**FOLK, "scales": {**scales, "energy": "3"}}, {**FOLK, "scales": {**scales, "energy": 3.5}},
            {**FOLK, "scales": {**scales, "energy": True}},
            {**FOLK, "scales": {k: v for k, v in scales.items() if k != "mood"}},
            {**FOLK, "scales": {**scales, "extra": 1}},
            {**FOLK, "genres": ["no_existe"]}, {**FOLK, "genres": ["folk", "folk"]},
            {**FOLK, "genres": ["folk", "rock", "pop", "latin", "reggae", "metal"]},
            {**FOLK, "artist_ids": ["art_inventado"]}, {**FOLK, "artist_ids": ["art_bad_bunny"] * 2},
            {**FOLK, "artist_ids": [f"art_{i}" for i in range(9)]},
            {"genres": [], "artist_ids": [], "scales": None}, {},
        ]
        for body in invalid:
            with self.subTest(body=body):
                self.assertEqual(self.client.put("/preferences/me", json=body, headers=a).status_code, 422)
        self.assertEqual(self.client.get("/preferences/me", headers=a).json()["status"], "unset")
        self.assertEqual(self.client.put("/preferences/me", json={"genres": ["folk"]}, headers=a).status_code, 200)
        self.assertEqual(self.client.put("/preferences/me", json={"scales": scales}, headers=a).status_code, 200)

    def test_options_list_stable_ids(self):
        body = self.client.get("/preferences/options").json()
        self.assertTrue(body["available"])
        ids = [a["id"] for a in body["artists"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("art_duki", ids)
        self.assertTrue(all(isinstance(a["id"], str) for a in body["artists"]))

    def test_catalog_without_future_dates_or_matches_falls_back(self):
        a, _ = self.signup("sin_fechas")
        self.client.put("/preferences/me", json=FOLK, headers=a)
        self.events = [card("p1", "José González", "K8vZ9175Yn7", "Folk", "2000-01-01"),
                       card("p2", "Karol G", "K8vZ917p3-V", "Latin", status="cancelled"),
                       card("p3", "Camilo", "K8vZ917_FzV", "Latin", tour="Camilo VIP Upgrade")]
        body = self.recs(a)
        self.assertEqual((body["available"], body["reason"], body["items"]), (False, "no_matches", []))
        self.events = []
        self.assertEqual(self.recs(a)["reason"], "no_matches")

    def test_catalog_failure_and_model_unavailable_fall_back(self):
        a, _ = self.signup("fallos")
        self.client.put("/preferences/me", json=FOLK, headers=a)
        from src.ticketmaster import TicketmasterError

        def broken(q, c):
            raise TicketmasterError(503, "x", "x")
        with patch.object(preferences, "get_public_concerts", broken):
            self.assertEqual(self.recs(a)["reason"], "catalog_unavailable")
        with patch.object(loader, "get_service", lambda: None):
            self.assertEqual(self.recs(a)["reason"], "model_unavailable")
            self.assertFalse(self.client.get("/preferences/options").json()["available"])
            self.assertEqual(self.client.put("/preferences/me", json=URBAN, headers=a).status_code, 503)
            # the saved answers survive an outage
            self.assertEqual(self.client.get("/preferences/me", headers=a).json()["genres"], FOLK["genres"])

    def test_artist_without_data(self):
        a, _ = self.signup("sin_datos")
        self.client.put("/preferences/me", json=URBAN, headers=a)
        self.events = [
            card("n1", "Ryan Castro", "TM-RC", "Latin"),                 # profile without vector -> genre signal
            card("n2", "Artista Desconocido", "TM-X", "Latin"),          # no profile, mapped provider genre
            card("n3", "Artista Misterioso", "TM-Y", "Undefined"),       # nothing usable -> excluded
            card("n4", "Bad Bunny", "TM-BB", "Latin"),                   # own vector
        ]
        items = {i["artist"]: i for i in self.recs(a)["items"]}
        self.assertEqual(set(items), {"Ryan Castro", "Artista Desconocido", "Bad Bunny"})
        self.assertEqual((items["Bad Bunny"]["source"], items["Ryan Castro"]["source"]), ("profile", "genre"))
        self.assertEqual(items["Artista Desconocido"]["source"], "genre")
        self.assertIsNone(items["Artista Desconocido"]["profile_id"])
        self.assertLess(items["Bad Bunny"]["distance"], items["Ryan Castro"]["distance"])

    def test_homonyms_are_never_matched_by_name(self):
        a, _ = self.signup("homonimos")
        self.client.put("/preferences/me", json=URBAN, headers=a)
        self.events = [card("h1", "Duki", "ID-1", "Undefined"), card("h2", "Duki", "ID-2", "Undefined")]
        items = self.recs(a)
        self.assertFalse(items["available"], "dos IDs distintos con el mismo nombre no usan el perfil por nombre")
        self.events = [card("h3", "Duki", "K8vZ917bvf7", "Undefined"), card("h4", "Duki", "ID-2", "Undefined")]
        items = self.recs(a)["items"]
        self.assertEqual({(i["artist_id"], i["source"]) for i in items}, {("K8vZ917bvf7", "profile")})


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.service = loader.load()

    def test_shipped_artifacts_are_verified_and_versioned_together(self):
        model = self.service.model
        manifest = json.loads((loader.ARTIFACTS / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(model.profiles_sha256, manifest["files"]["artist_profiles.json"])
        self.assertTrue(model.version.startswith("kmeans-"))
        self.assertGreaterEqual(len(model.centroids), 3)
        self.assertTrue(model.self_check)

    def test_tampered_or_incomplete_artifacts_are_rejected(self):
        for change in ("model", "profiles", "manifest", "missing"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                shutil.copytree(loader.ARTIFACTS, tmp, dirs_exist_ok=True)
                target = {"model": "model.json", "profiles": "artist_profiles.json"}.get(change)
                if change == "manifest":
                    path = Path(tmp) / "manifest.json"
                    manifest = json.loads(path.read_text(encoding="utf-8"))
                    manifest["files"]["model.json"] = "0" * 64
                    path.write_text(json.dumps(manifest), encoding="utf-8")
                elif target:
                    with open(Path(tmp) / target, "ab") as handle:
                        handle.write(b" ")
                else:
                    (Path(tmp) / "model.json").unlink()
                with self.assertRaises((ValueError, OSError)):
                    loader.load(tmp)
        with patch.object(loader, "ARTIFACTS", Path("/nonexistent")):
            loader.get_service.cache_clear()
            self.assertIsNone(loader.get_service())
        loader.get_service.cache_clear()

    def test_invalid_model_contents_are_rejected(self):
        data = json.loads((loader.ARTIFACTS / "model.json").read_text(encoding="utf-8"))
        for mutate in (lambda d: d.update(schema=2), lambda d: d["centroids"].pop(),
                       lambda d: d["preprocessing"]["scale"].__setitem__(0, 0),
                       lambda d: d["weights"].update(scales=-1), lambda d: d.pop("genre_prototypes")):
            broken = json.loads(json.dumps(data))
            mutate(broken)
            with self.assertRaises(engine.ArtifactError):
                engine.Model(broken)

    def test_small_dataset_still_ranks(self):
        model, store = self.service.model, self.service.store
        vector = engine.user_vector(model, store, ["folk"], [], None)
        events = [card("s1", "José González", "K8vZ9175Yn7", "Folk")]
        _, items = engine.rank(model, store, vector, events, date(2099, 1, 1))
        self.assertEqual([i["artist"] for i in items], ["José González"])
        self.assertEqual(engine.rank(model, store, vector, [], date(2099, 1, 1))[1], [])

    def test_vector_combination(self):
        model, store = self.service.model, self.service.store
        self.assertIsNone(engine.user_vector(model, store, [], [], None))
        scales_only = engine.user_vector(model, store, [], [], [1, 3, 5, 3])
        for got, want in zip(scales_only, (0.0, 0.5, 1.0, 0.5)):
            self.assertAlmostEqual(got, want, places=9)
        folk = model.genre_prototypes["folk"]
        genre_only = engine.user_vector(model, store, ["folk"], [], None)
        for got, want in zip(genre_only, folk):
            self.assertAlmostEqual(got, want, places=9)
        w = model.weights
        both = engine.user_vector(model, store, ["folk"], [], [5, 5, 5, 5])
        expected = [(w["scales"] * 1.0 + w["genres"] * f) / (w["scales"] + w["genres"]) for f in folk]
        for got, want in zip(both, expected):
            self.assertAlmostEqual(got, want, places=9)
        # an artist without a vector contributes its curated genre prototype
        no_vec = engine.user_vector(model, store, [], ["art_ryan_castro"], None)
        for got, want in zip(no_vec, model.genre_prototypes["latin"]):
            self.assertAlmostEqual(got, want, places=9)

    def test_ties_are_deterministic(self):
        model, store = self.service.model, self.service.store
        vector = engine.user_vector(model, store, ["rock"], [], None)
        events = [card(f"t{i}", f"Sin perfil {i}", f"TM-{i}", "Rock") for i in range(6)]
        orders = set()
        for shuffled in (events, list(reversed(events)), events[3:] + events[:3]):
            _, items = engine.rank(model, store, vector, shuffled, date(2099, 1, 1))
            orders.add(tuple(i["artist_id"] for i in items))
        self.assertEqual(len(orders), 1)
        self.assertEqual(next(iter(orders)), tuple(f"TM-{i}" for i in range(6)))

    def test_profiles_are_clean_and_do_not_depend_on_spotify(self):
        store = self.service.store
        self.assertGreaterEqual(len(store.by_id), 100)
        for artist in store.by_id.values():
            self.assertRegex(artist.id, r"^art_[a-z0-9_]+$")
            self.assertTrue(set(artist.genres) <= set(store.genres), artist.id)
        text = (loader.ARTIFACTS / "artist_profiles.json").read_text(encoding="utf-8")
        self.assertNotIn("track_id", text)
        self.assertNotIn("spotify.com", text)


if __name__ == "__main__":
    unittest.main()
