import copy
import json
import unittest
from datetime import datetime, timezone, timedelta, date, time
from unittest.mock import patch, AsyncMock
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from src.database import Base, get_db
from src import models
from src.catalog import query_catalog, visible, sync_status
from src.ticketmaster import discover_events, map_event, TicketmasterError, purchase_url
from src.sync_ticketmaster import apply_snapshot, sync_once
from src.routers import assistant
from src.main import app
from src.config import settings
from src.security import get_current_user

UTC = timezone.utc
NOW = datetime(2099, 1, 1, 15, tzinfo=UTC)

def event(identity="one", day="2099-02-01", hour="20:00:00"):
    start = {"localDate": day}
    if hour:
        start["localTime"] = hour
    return {"id": identity, "name": "Festival fixture", "dates": {"start": start, "timezone": "America/Bogota", "status": {"code": "onsale"}},
        "_embedded": {"attractions": [{"id": "artist1", "name": "Fixture Artist", "classifications": [{"segment": {"name": "Music"}}]}],
            "venues": [{"id": "venue1", "name": "Fixture Venue", "city": {"name": "Bogota"}, "country": {"countryCode": "CO"}}]},
        "url": "https://www.ticketmaster.com/event/one"}

class DiscoveryTests(unittest.TestCase):
    def test_two_pages_and_invalid_second_page(self):
        records = [event(str(i)) for i in range(201)]
        def request(params):
            n = params["page"]
            self.assertEqual(params["countryCode"], "CO")
            return {"page": {"number": n, "size": 200, "totalPages": 2, "totalElements": 201}, "_embedded": {"events": records[n*200:(n+1)*200]}}
        rows = discover_events("CO", NOW, NOW+timedelta(days=365), request)
        self.assertEqual(len(rows), 201)
        def fail(params):
            if params["page"] == 1:
                raise TicketmasterError(503, "network", "unavailable")
            return request(params)
        with self.assertRaises(TicketmasterError):
            discover_events("CO", NOW, NOW+timedelta(days=365), fail)
        bad = lambda p: {"page": {"number": 0, "size": 200, "totalPages": 2, "totalElements": 201}, "_embedded": {"events": []}}
        with self.assertRaises(TicketmasterError):
            discover_events("CO", NOW, NOW+timedelta(days=365), bad)

    def test_empty_and_split_deduplication(self):
        empty = lambda p: {"page": {"number": 0, "size": 200, "totalPages": 0, "totalElements": 0}}
        self.assertEqual(discover_events("CO", NOW, NOW+timedelta(days=2), empty), [])
        calls = []
        def request(params):
            calls.append(params)
            total = 1001 if len(calls) == 1 else 1
            return {"page": {"number": 0, "size": 200, "totalPages": 6 if total == 1001 else 1, "totalElements": total}, "_embedded": {"events": [event()]}}
        self.assertEqual(len(discover_events("CO", NOW, NOW+timedelta(days=2), request)), 1)
        self.assertEqual(len(calls), 3)

    def test_mapping_partial_unknown_and_security(self):
        raw = event(hour=None)
        raw["_embedded"]["venues"] = []
        mapped = map_event(raw, "CO")
        self.assertIsNone(mapped["event_time"])
        self.assertIsNone(mapped["starts_at"])
        self.assertIsNone(mapped["provider_price"])
        self.assertIsNone(mapped["image_url"])
        self.assertEqual(mapped["venue"]["name"], "Recinto desconocido")
        self.assertIsNone(purchase_url("https://ticketmaster.com.evil.example/event"))
        self.assertIsNone(purchase_url("javascript:alert(1)"))
        self.assertIsNone(purchase_url("https://user@ticketmaster.com/event"))
        for status in ("cancelled", "postponed"):
            raw["dates"]["status"]["code"] = status
            self.assertIsNone(map_event(raw, "CO"))
        raw["dates"]["status"]["code"] = "rescheduled"
        self.assertIsNotNone(map_event(raw, "CO"))
        raw["_embedded"]["attractions"] = []
        self.assertIsNone(map_event(raw, "CO"))

class CatalogTests(unittest.TestCase):
    def setUp(self):
        scope = patch.multiple(settings, ticketmaster_scope="country", ticketmaster_country_code="CO")
        scope.start()
        self.addCleanup(scope.stop)
        self.engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()
    def snapshot(self, records):
        apply_snapshot(self.db, [m for e in records if (m := map_event(e, "CO"))], {e["id"] for e in records}, "CO", NOW, NOW+timedelta(days=365), NOW)
        self.db.commit()
    def test_idempotence_update_absence_and_clock(self):
        raw = event()
        self.snapshot([raw])
        c = self.db.query(models.Concert).one()
        identity = c.id
        self.snapshot([raw])
        self.assertEqual(self.db.query(models.Concert).count(), 1)
        raw["dates"]["start"]["localDate"] = "2099-03-01"
        raw["_embedded"]["venues"][0]["name"] = "Changed venue"
        self.snapshot([raw])
        self.assertEqual(c.id, identity)
        self.assertEqual(c.event_date, date(2099, 3, 1))
        self.assertEqual(c.venue.name, "Changed venue")
        self.assertFalse(visible(c, datetime(2100, 1, 1, tzinfo=UTC)))
        self.snapshot([])
        self.assertEqual(c.catalog_status, "active")
        self.snapshot([])
        self.assertEqual(c.catalog_status, "inactive")
        self.assertEqual(sync_status(self.db, NOW)[0], "updated")
        self.assertEqual(self.db.get(models.CatalogSync, "CO").event_count, 0)
    def test_stable_order_unknown_hour_and_legacy(self):
        self.snapshot([event("early", hour="18:00:00"), event("late", hour="22:00:00"), event("unknown", hour=None), event("distant", "2099-12-01")])
        near, _ = query_catalog(self.db, now=NOW)
        far, _ = query_catalog(self.db, order="latest_first", now=NOW)
        self.assertEqual([c.external_id for c in near], ["early", "late", "unknown", "distant"])
        self.assertEqual([c.external_id for c in far], ["distant", "late", "early", "unknown"])
        unknown = near[2]
        self.assertTrue(visible(unknown, datetime(2099,2,2,4,59,tzinfo=UTC)))
        self.assertFalse(visible(unknown, datetime(2099,2,2,5,tzinfo=UTC)))
        self.assertEqual(query_catalog(self.db, city="other", now=NOW)[1], 0)
        self.assertEqual(query_catalog(self.db, artist="Fixture", now=NOW)[1], 4)
        near[0].source = "legacy"
        self.db.commit()
        self.assertEqual(query_catalog(self.db, now=NOW)[1], 3)
    def test_actual_instants_across_timezones(self):
        japan, usa = event("japan", "2099-02-02", "01:00:00"), event("usa", "2099-02-01", "22:00:00")
        japan["dates"]["timezone"] = "Asia/Tokyo"
        japan["dates"]["start"]["dateTime"] = "2099-02-01T16:00:00Z"
        usa["dates"]["timezone"] = "America/New_York"
        usa["dates"]["start"]["dateTime"] = "2099-02-02T03:00:00Z"
        self.snapshot([japan, usa])
        rows, _ = query_catalog(self.db, order="latest_first", now=NOW)
        self.assertEqual([c.external_id for c in rows], ["usa", "japan"])

    def test_public_api_and_external_order(self):
        self.snapshot([event()])
        c = self.db.query(models.Concert).one()
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: models.User(id=1)
        with TestClient(app) as client:
            rows = client.get('/concerts').json()
            self.assertEqual(len(rows), 1)
            self.assertIsNone(rows[0]['price_from'])
            self.assertIsNone(rows[0]['tickets_available'])
            self.assertEqual(client.get(f'/concerts/{c.id}').status_code, 200)
            with patch('src.ticketmaster.get_artist_upcoming_events', return_value={'artist': 'Fixture Artist', 'source': 'ticketmaster', 'status': 'no_events', 'events': [], 'message': None}) as upcoming:
                self.assertEqual(client.get(f'/concerts/{c.id}/upcoming-events').status_code, 200)
                upcoming.assert_called_once_with('Fixture Artist', 'artist1')
            response = client.post('/orders', json={'concert_id': c.id, 'payment_method': 'card', 'items': [{'ticket_type_id': 1, 'quantity': 1}]})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(client.post('/concerts', json={'artist': 'a', 'tour_name': 't', 'genre': 'g', 'venue_id': c.venue_id, 'event_date': '2099-01-01', 'event_time': '20:00:00'}).status_code, 403)
    def test_chat_renders_catalog_and_truncates(self):
        self.assertEqual(sync_status(self.db)[0], 'unavailable')
        self.snapshot([event(str(i), '2099-02-01') for i in range(21)] + [event('far', '2099-12-01')])
        with patch.object(assistant, 'SessionLocal', return_value=Session(self.engine)):
            reply = assistant.catalog_reply(assistant.CatalogIntent(intent='concerts', order='latest_first'))
        self.assertIn('20 de 22', reply)
        self.assertIn('01/12/2099', reply.splitlines()[1])
    def test_chat_auth_and_invalid_json(self):
        assistant.request_times.clear(); assistant.requests_by_user.clear()
        app.dependency_overrides[get_db] = lambda: self.db
        with TestClient(app) as client:
            self.assertEqual(client.post('/assistant/chat', json={'message': 'hola'}).status_code, 401)
            app.dependency_overrides[get_current_user] = lambda: models.User(id=1)
            response = httpx.Response(200, json={'message': {'content': 'invalid'}}, request=httpx.Request('POST','http://ollama/api/chat'))
            with patch.object(settings, 'ollama_base_url', 'http://ollama'), patch('httpx.AsyncClient.post', new=AsyncMock(return_value=response)):
                self.assertEqual(client.post('/assistant/chat', json={'message':'conciertos'}).status_code, 502)


class ArtistOriginTests(unittest.TestCase):
    def test_only_verified_selected_singers_and_bad_bunny(self):
        from src.artist_origins import discover_selected_artists
        selected = {'id': 'Qtest', 'origins': ['PR'], 'name': 'Bad Bunny', 'names': ['Bad Bunny'], 'sitelinks': 100, 'source': 'https://www.wikidata.org/wiki/Qtest'}
        eligible = event('bunny')
        eligible['_embedded']['attractions'][0]['name'] = 'Bad Bunny'
        unknown = event('unknown')
        unknown['_embedded']['attractions'][0]['name'] = 'Unknown nationality'
        with patch('src.artist_origins.artist_registry', return_value=[selected]), patch('src.artist_origins.discover_events', return_value=[eligible, unknown]), patch('src.artist_origins._event_detail', return_value={}):
            events, mapped, count = discover_selected_artists(NOW, NOW+timedelta(days=365))
        self.assertEqual(count, 1)
        self.assertEqual(len(events), 2)
        self.assertEqual([r['external_id'] for r in mapped], ['bunny'])
        self.assertIn('PR', mapped[0]['artist_provenance'])

    def test_don_omar_and_global_detail_enrichment(self):
        from src.artist_origins import _include_don_omar, discover_selected_artists
        candidates = {}
        _include_don_omar(candidates, ["CO"])
        self.assertEqual(candidates, {})
        _include_don_omar(candidates, ["PR"])
        _include_don_omar(candidates, ["PR"])
        self.assertEqual(candidates["Q310539"]["origins"], ["PR"])
        rows = [event("denver"), event("another")]
        for row in rows:
            row["_embedded"]["attractions"][0]["name"] = "Don Omar"
            row["_embedded"]["venues"] = []
            row["priceRanges"] = None

        def detail(event_id):
            result = {"id": event_id, "_embedded": {"venues": [{"name": "Ball Arena"}]}}
            if event_id == "another":
                result["priceRanges"] = [{"min": 75, "currency": "USD"}, {"min": 95, "currency": "USD"}]
            return result

        with patch('src.artist_origins.artist_registry', return_value=list(candidates.values())), patch('src.artist_origins.discover_events', return_value=rows), patch('src.artist_origins._event_detail', side_effect=detail) as lookup:
            _, mapped, _ = discover_selected_artists(NOW, NOW+timedelta(days=365))
        self.assertEqual(lookup.call_count, 2)
        self.assertEqual(mapped[0]["venue"]["name"], "Ball Arena")
        self.assertIsNone(mapped[0]["provider_price"])
        self.assertEqual(mapped[1]["provider_price"], 75)
        self.assertEqual(mapped[1]["currency"], "USD")


class IntentOrderTests(unittest.TestCase):
    def test_explicit_time_direction_overrides_inverted_classifier(self):
        for phrase in ('Que conciertos hay proximos de mayor a menor en tiempo al dia actual?', 'Del mas lejano al mas cercano', 'Orden cronologico descendente'):
            intent = assistant.CatalogIntent(intent='concerts', order='nearest_first')
            self.assertEqual(assistant.validate_explicit_order(phrase, intent).order, 'latest_first')
        intent = assistant.CatalogIntent(intent='concerts', order='latest_first')
        self.assertEqual(assistant.validate_explicit_order('Dame los mas cercanos primero', intent).order, 'nearest_first')
