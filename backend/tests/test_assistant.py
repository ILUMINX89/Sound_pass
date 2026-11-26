"""Pruebas aisladas del asistente SoundPass AI: sin red ni BD real."""
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.database import Base, get_db
from src.main import app
from src.routers import assistant


EVENTS = [
    {"id": "e1", "artist": "Bob Dylan", "event_date": "2099-03-10", "event_time": "19:00:00",
     "venue": {"name": "bp pulse LIVE", "city": "Birmingham"}},
    {"id": "e2", "artist": "Karol G", "event_date": "2099-08-20", "event_time": "21:00:00",
     "venue": {"name": "Estadio", "city": "Madrid"}},
    {"id": "e3", "artist": "Pasado", "event_date": "2000-01-01", "event_time": "20:00:00",
     "venue": {"name": "Viejo", "city": "Lima"}},
]


def mock_ollama(payload):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"message": {"content": json.dumps(payload)}}
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post.return_value = resp
    return client


class AssistantTests(unittest.TestCase):
    def setUp(self):
        assistant.request_times.clear()
        assistant.requests_by_user.clear()
        assistant.active_requests = 0
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        def test_db():
            yield self.db
        app.dependency_overrides[get_db] = test_db
        self.client = TestClient(app)
        data = {"full_name": "Ana AI", "email": "ana.ai@example.com", "password": "Password123!"}
        self.client.post("/auth/register", json=data)
        token = self.client.post("/auth/login", json=data).json()["access_token"]
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def test_requires_auth(self):
        r = self.client.post("/assistant/chat", json={"message": "¿Qué conciertos próximos hay?"})
        self.assertEqual(r.status_code, 401)

    def test_disabled_when_ollama_url_empty(self):
        with patch.object(assistant.settings, "ollama_base_url", ""):
            r = self.client.post("/assistant/chat", headers=self.headers, json={"message": "hola"})
            self.assertEqual(r.status_code, 503)

    def test_concerts_intent_returns_real_catalog_dates_and_order(self):
        with patch.object(assistant.settings, "ollama_base_url", "http://ollama.test:11434"), \
                patch.object(assistant.httpx, "AsyncClient", return_value=mock_ollama({"intent": "concerts", "order": "nearest_first"})), \
                patch.object(assistant, "artist_catalog", lambda db: {}), \
                patch.object(assistant, "get_public_concerts", lambda q, c: list(EVENTS)):
            r = self.client.post("/assistant/chat", headers=self.headers, json={"message": "¿Qué conciertos próximos hay?"})
            self.assertEqual(r.status_code, 200)
            reply = r.json()["reply"]
            self.assertIn("Bob Dylan", reply)
            self.assertIn("Karol G", reply)
            self.assertNotIn("Pasado", reply)
            self.assertLess(reply.index("Bob Dylan"), reply.index("Karol G"))

    def test_explicit_latest_order_and_city_filter(self):
        with patch.object(assistant.settings, "ollama_base_url", "http://ollama.test:11434"), \
                patch.object(assistant.httpx, "AsyncClient", return_value=mock_ollama({"intent": "concerts", "order": "nearest_first", "city": "Madrid"})), \
                patch.object(assistant, "artist_catalog", lambda db: {}), \
                patch.object(assistant, "get_public_concerts", lambda q, c: list(EVENTS)):
            r = self.client.post("/assistant/chat", headers=self.headers, json={"message": "Conciertos en Madrid de mayor a menor en tiempo"})
            self.assertEqual(r.status_code, 200)
            self.assertIn("Karol G", r.json()["reply"])
            self.assertNotIn("Bob Dylan", r.json()["reply"])

    def test_help_and_ollama_errors(self):
        with patch.object(assistant.settings, "ollama_base_url", "http://ollama.test:11434"), \
                patch.object(assistant.httpx, "AsyncClient", return_value=mock_ollama({"intent": "help", "order": "nearest_first"})):
            r = self.client.post("/assistant/chat", headers=self.headers, json={"message": "¿Cómo descargo mis boletos?"})
            self.assertEqual(r.status_code, 200)
            self.assertIn("Mis boletos", r.json()["reply"])

        failing = AsyncMock()
        failing.__aenter__.return_value = failing
        failing.post.side_effect = httpx.ConnectError("refused")
        with patch.object(assistant.settings, "ollama_base_url", "http://ollama.test:11434"), \
                patch.object(assistant.httpx, "AsyncClient", return_value=failing):
            r = self.client.post("/assistant/chat", headers=self.headers, json={"message": "hola"})
            self.assertEqual(r.status_code, 502)


if __name__ == "__main__":
    unittest.main()
