"""Pruebas aisladas: no conectan a la BD configurada ni a servicios externos."""
import os
import subprocess
import sys
import secrets
import unittest
from datetime import date, time, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src import models
from src.config import Settings, settings
from src.database import Base, get_db
from src.main import app


class SettingsTests(unittest.TestCase):
    def test_public_key_validation(self):
        for env in ('staging', 'production'):
            for key in ('', 'change-this-to-a-long-random-string', 'a' * 64,
                        'replace_with_generated_random_key'):
                with self.subTest(env=env, key=key), self.assertRaises(ValidationError):
                    Settings(_env_file=None, app_env=env, secret_key=key,
                             database_url='sqlite://', allowed_origins='')
            valid = Settings(_env_file=None, app_env=env, secret_key=secrets.token_urlsafe(48),
                             database_url='sqlite://', allowed_origins='https://example.invalid')
            self.assertTrue(valid.is_public)

    def test_public_database_and_origins(self):
        for env in ('staging', 'production'):
            options = dict(_env_file=None, app_env=env,
                           secret_key=secrets.token_urlsafe(48), allowed_origins='')
            with self.assertRaises(ValidationError):
                Settings(**options)
            for origin in ('http://example.com', '*', 'https://*.example.com',
                           'https://user:password@example.com', 'https://example.com/path',
                           'https://example.com?query=1', 'https://example.com#fragment'):
                with self.subTest(env=env, origin=origin), self.assertRaises(ValidationError):
                    Settings(**(options | {'database_url': 'sqlite://', 'allowed_origins': origin}))
            self.assertEqual(Settings(**options, database_url='sqlite://').cors_origins, [])

    def test_documentation_profiles(self):
        # Cada arranque tiene su propio registro de métricas de Prometheus.
        code = """
from fastapi.testclient import TestClient
from src.config import settings
from src.main import app
with TestClient(app) as client:
    for path in ('/docs', '/redoc', '/openapi.json'):
        assert client.get(path).status_code == (404 if settings.is_public else 200), path
    assert client.get('/health').status_code == 200
    assert client.get('/metrics').status_code == 200
    assert not app.debug
"""
        for env in ('local', 'test', 'staging', 'production'):
            with self.subTest(env=env):
                result = subprocess.run(
                    [sys.executable, '-c', code], capture_output=True, text=True,
                    timeout=30, env=os.environ | {
                        'APP_ENV': env, 'SECRET_KEY': secrets.token_urlsafe(48),
                        'DATABASE_URL': 'sqlite://', 'ALLOWED_ORIGINS': '',
                    },
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False},
                                    poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        def test_db():
            yield self.db
        app.dependency_overrides[get_db] = test_db
        self.client = TestClient(app)
        venue = models.Venue(name='Prueba', city='Bogotá', address='Calle de prueba', capacity=100)
        concert = models.Concert(artist='Artista', tour_name='Gira', genre='Rock', venue=venue,
                                 event_date=date(2099, 1, 1), event_time=time(20))
        ticket = models.TicketType(concert=concert, name='General', price=10000, quantity_available=10)
        self.db.add_all([venue, concert, ticket]); self.db.commit()
        self.concert_id, self.ticket_id = concert.id, ticket.id
        self.headers = []
        for name in ('uno', 'dos'):
            data = {'full_name': name, 'email': f'{name}@example.com', 'password': 'Password123!'}
            self.assertEqual(self.client.post('/auth/register', json=data).status_code, 201)
            response = self.client.post('/auth/login', json=data)
            self.assertEqual(response.status_code, 200)
            self.headers.append({'Authorization': 'Bearer ' + response.json()['access_token']})

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); self.db.close(); self.engine.dispose()

    def test_jwt_rejections(self):
        paths = [('/auth/me', 'get'), ('/orders/me', 'get'), ('/orders/1', 'get'),
                 ('/orders/1/cancel', 'post'), ('/orders/1/tickets/pdf', 'get'), ('/orders', 'post')]
        claims = [({'sub': '1', 'exp': datetime.now(timezone.utc) - timedelta(minutes=1)}, settings.secret_key),
                  ({'sub': 'no-numero', 'exp': 4102444800}, settings.secret_key),
                  ({'sub': '999999999999999999999', 'exp': 4102444800}, settings.secret_key),
                  ({'sub': '999', 'exp': 4102444800}, settings.secret_key),
                  ({'sub': '1'}, settings.secret_key),
                  ({'exp': 4102444800}, settings.secret_key),
                  ({'sub': '1', 'exp': None}, settings.secret_key),
                  ({'sub': '1', 'exp': []}, settings.secret_key),
                  ({'sub': '1', 'exp': {}}, settings.secret_key),
                  ({'sub': '0', 'exp': 4102444800}, settings.secret_key),
                  ({'sub': '١', 'exp': 4102444800}, settings.secret_key),
                  ({'sub': '1', 'exp': 4102444800}, 'wrong-key')]
        headers = [{}, {'Authorization': 'Bearer invalid'}] + [
            {'Authorization': 'Bearer ' + jwt.encode(c, key, algorithm='HS256')} for c, key in claims]
        for path, method in paths:
            for header in headers:
                with self.subTest(path=path, header_kind=bool(header)):
                    self.assertEqual(getattr(self.client, method)(path, headers=header).status_code, 401)

    def test_two_accounts_full_flow(self):
        self.assertEqual(self.client.get('/concerts').status_code, 200)
        self.assertEqual(self.client.get('/venues').status_code, 200)
        orders = []
        for headers in self.headers:
            response = self.client.post('/orders', headers=headers, json={
                'concert_id': self.concert_id, 'payment_method': 'card',
                'items': [{'ticket_type_id': self.ticket_id, 'quantity': 1}]})
            self.assertEqual(response.status_code, 201, response.text)
            orders.append(response.json()['id'])
        for index, headers in enumerate(self.headers):
            own, other = orders[index], orders[1 - index]
            self.assertEqual(self.client.get(f'/orders/{own}', headers=headers).status_code, 200)
            self.assertEqual([o['id'] for o in self.client.get('/orders/me', headers=headers).json()], [own])
            for suffix, method in (('', 'get'), ('/cancel', 'post'), ('/tickets/pdf', 'get')):
                self.assertEqual(getattr(self.client, method)(f'/orders/{other}{suffix}', headers=headers).status_code, 404)
            self.db.expire_all()
            self.assertEqual(self.db.get(models.Order, other).status, 'confirmed')
            self.assertEqual(self.db.query(models.IssuedTicket).count(), index)
            pdf = self.client.get(f'/orders/{own}/tickets/pdf', headers=headers)
            self.assertEqual(pdf.status_code, 200)
            self.assertTrue(pdf.content.startswith(b'%PDF'))
        for own, headers in zip(orders, self.headers):
            self.assertEqual(self.client.post(f'/orders/{own}/cancel', headers=headers).status_code, 200)
            self.assertEqual(self.client.get(f'/orders/{own}/tickets/pdf', headers=headers).status_code, 409)
            history = self.client.get('/orders/me?status_filter=cancelled', headers=headers).json()
            self.assertEqual([o['id'] for o in history], [own])
        self.db.expire_all()
        self.assertEqual(self.db.get(models.TicketType, self.ticket_id).quantity_available, 10)
