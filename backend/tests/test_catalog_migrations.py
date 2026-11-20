"""PostgreSQL-only acceptance tests; require a dedicated disposable database."""
import os
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from src.models import Concert
from src.sync_ticketmaster import apply_snapshot
from src.ticketmaster import map_event, TicketmasterError
from src.config import settings
from src.sync_ticketmaster import sync_once, LOCK
from unittest.mock import patch
from test_catalog import event, NOW

@unittest.skipUnless(os.getenv("CATALOG_TEST_DATABASE_URL"), "isolated PostgreSQL not configured")
class MigrationTests(unittest.TestCase):
    def test_new_and_historical_schema(self):
        engine = create_engine(os.environ["CATALOG_TEST_DATABASE_URL"])
        root = Path('/fixtures')
        schema = (root/'schema.sql').read_text()
        migration = (root/'migrations/002_ticketmaster_catalog.sql').read_text()
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            self.assertEqual(conn.exec_driver_sql('SELECT current_database()').scalar(), 'catalog_test')
            conn.exec_driver_sql('DROP SCHEMA IF EXISTS catalog_legacy_test CASCADE')
            conn.exec_driver_sql('DROP SCHEMA IF EXISTS catalog_new_test CASCADE')
            conn.exec_driver_sql('CREATE SCHEMA catalog_legacy_test')
            conn.exec_driver_sql('SET search_path TO catalog_legacy_test')
            conn.exec_driver_sql(schema.split('BEGIN;')[0])
            conn.exec_driver_sql((root/'dev_seed.sql').read_text())
            before = conn.exec_driver_sql('SELECT id,concert_id,user_id FROM orders ORDER BY id').all()
            counts = conn.exec_driver_sql('SELECT (SELECT count(*) FROM users),(SELECT count(*) FROM concerts),(SELECT count(*) FROM order_items)').one()
            conn.exec_driver_sql(migration)
            conn.exec_driver_sql(migration)
            self.assertEqual(before, conn.exec_driver_sql('SELECT id,concert_id,user_id FROM orders ORDER BY id').all())
            self.assertEqual(counts, conn.exec_driver_sql('SELECT (SELECT count(*) FROM users),(SELECT count(*) FROM concerts),(SELECT count(*) FROM order_items)').one())
            self.assertEqual(conn.exec_driver_sql("SELECT count(*) FROM concerts WHERE source <> 'legacy' OR catalog_status <> 'inactive'").scalar(), 0)
            conn.exec_driver_sql('CREATE SCHEMA catalog_new_test')
            conn.exec_driver_sql('SET search_path TO catalog_new_test')
            conn.exec_driver_sql(schema)
            conn.exec_driver_sql(migration)
            self.assertEqual(conn.exec_driver_sql('SELECT count(*) FROM concerts').scalar(), 0)
        with engine.connect() as conn:
            conn.execute(text('SET search_path TO catalog_new_test')); conn.commit()
            with Session(bind=conn) as db:
                mapped = map_event(event(), 'CO')
                for _ in range(2):
                    apply_snapshot(db, [mapped], {'one'}, 'CO', NOW, NOW+timedelta(days=365), NOW)
                    db.commit()
                self.assertEqual(db.query(Concert).count(), 1)
                c = db.query(Concert).one()
                identity = c.id
                mapped['tour_name'] = 'Updated'
                apply_snapshot(db, [mapped], {'one'}, 'CO', NOW, NOW+timedelta(days=365), NOW)
                db.commit()
                self.assertEqual(c.id, identity)
                self.assertEqual(c.tour_name, 'Updated')
        isolated = create_engine(os.environ["CATALOG_TEST_DATABASE_URL"], connect_args={"options": "-csearch_path=catalog_new_test"})
        with patch("src.sync_ticketmaster.engine", isolated), patch.object(settings, "ticketmaster_api_key", "fixture_key"), patch.object(settings, "ticketmaster_scope", "country"):
            with patch("src.sync_ticketmaster.discover_events", side_effect=TicketmasterError(503, "page_two_failure", "unavailable")):
                self.assertFalse(sync_once())
            with isolated.connect() as first:
                self.assertTrue(first.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK}).scalar())
                with patch("src.sync_ticketmaster.discover_events") as discover:
                    self.assertFalse(sync_once())
                    discover.assert_not_called()
                first.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK})
            with Session(isolated) as db:
                self.assertEqual(db.query(Concert).count(), 1)
                self.assertEqual(db.query(Concert).one().tour_name, "Updated")
                self.assertEqual(db.query(Concert).one().catalog_status, "active")
        isolated.dispose()
        engine.dispose()
