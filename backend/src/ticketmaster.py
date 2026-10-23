"""Consulta informativa de próximos conciertos en Ticketmaster."""

import json
import unicodedata
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from src.config import settings


class TicketmasterError(Exception):
    def __init__(self, status_code, code, message):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


_cache = OrderedDict()
_lock = Lock()
_CACHE_SECONDS = 900
_CACHE_MAX = 128


def _normalize(value):
    text = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in text if c.isalnum())


def _request(resource, params):
    params = {
        **params,
        "apikey": settings.ticketmaster_api_key.strip(),
    }
    url = (
        "https://app.ticketmaster.com/discovery/v2/"
        + resource
        + ".json?"
        + urlencode(params)
    )
    try:
        with urlopen(url, timeout=10) as response:
            data = json.load(response)
    except HTTPError as error:
        if error.code == 429:
            message = "Ticketmaster alcanzó su límite de consultas."
        elif error.code in (401, 403):
            message = "Ticketmaster rechazó las credenciales configuradas."
        else:
            message = "Ticketmaster no está disponible."
        raise TicketmasterError(
            503, "ticketmaster_unavailable", message
        ) from None
    except (URLError, TimeoutError, OSError):
        raise TicketmasterError(
            503,
            "ticketmaster_unavailable",
            "No fue posible conectar con Ticketmaster.",
        ) from None
    except (ValueError, UnicodeError):
        raise TicketmasterError(
            502,
            "ticketmaster_invalid_response",
            "Ticketmaster devolvió una respuesta inválida.",
        ) from None

    if not isinstance(data, dict) or "fault" in data or "errors" in data:
        raise TicketmasterError(
            502,
            "ticketmaster_invalid_response",
            "Ticketmaster devolvió una respuesta inválida.",
        )
    return data


def _items(data, name):
    embedded = data.get("_embedded", {})
    if not isinstance(embedded, dict):
        raise ValueError("Invalid embedded data")
    items = embedded.get(name, [])
    if not isinstance(items, list) or any(
        not isinstance(item, dict) for item in items
    ):
        raise ValueError("Invalid item list")
    return items


def _lookup(artist):
    result = {
        "artist": artist,
        "source": "ticketmaster",
        "status": "not_found",
        "events": [],
        "message": "No se encontró al artista en Ticketmaster.",
    }
    if not _normalize(artist):
        return result

    data = _request("attractions", {
        "keyword": artist,
        "classificationName": "music",
        "size": 50,
    })
    matches = {
        item["id"]: item
        for item in _items(data, "attractions")
        if item.get("id")
        and _normalize(item.get("name") or "") == _normalize(artist)
    }

    if not matches:
        return result

    if len(matches) > 1:
        result.update(
            status="ambiguous",
            message="Se encontraron varios artistas con el mismo nombre.",
        )
        return result

    artist_id = next(iter(matches))
    data = _request("events", {
        "attractionId": artist_id,
        "startDateTime": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "includeTBA": "no",
        "includeTBD": "no",
        "size": 50,
        "sort": "date,asc",
    })

    seen = set()
    events = []

    for event in _items(data, "events"):
        # Excluir modalidades comerciales que repiten el concierto.
        event_name = " ".join(
            (event.get("name") or "").casefold().split()
        )
        if any(label in event_name for label in (
            "suite reservation",
            "cannot split by day",
            "2-day ticket",
            "2 day ticket",
        )):
            continue
        event_id = event.get("id")
        dates = event.get("dates") or {}
        status = (dates.get("status") or {}).get("code")

        if (
            not event_id
            or event_id in seen
            or status in {"cancelled", "canceled", "postponed"}
        ):
            continue

        start = dates.get("start") or {}
        if (
            not start.get("localDate")
            or start.get("dateTBD")
            or start.get("dateTBA")
        ):
            continue

        venues = _items(event, "venues")
        venue = venues[0] if venues else {}

        events.append({
            "id": event_id,
            "date": start["localDate"],
            "time": (
                None
                if start.get("timeTBA") or start.get("noSpecificTime")
                else start.get("localTime")
            ),
            "timezone": dates.get("timezone") or venue.get("timezone"),
            "city": (venue.get("city") or {}).get("name"),
            "country": (venue.get("country") or {}).get("name"),
            "venue": venue.get("name"),
        })
        seen.add(event_id)

        if len(events) == 10:
            break

    result.update(
        status="ok" if events else "no_events",
        events=events,
        message=(
            None
            if events
            else "No encontramos próximos conciertos en Ticketmaster."
        ),
    )
    return result


def get_artist_upcoming_events(artist):
    if not settings.ticketmaster_api_key.strip():
        raise TicketmasterError(
            503,
            "ticketmaster_not_configured",
            "Ticketmaster no está configurado.",
        )

    artist = artist.strip()
    cache_key = artist.casefold()

    with _lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > monotonic():
            _cache.move_to_end(cache_key)
            return deepcopy(cached[1])

    try:
        result = _lookup(artist)
    except TicketmasterError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError):
        raise TicketmasterError(
            502,
            "ticketmaster_invalid_response",
            "Ticketmaster devolvió datos inesperados.",
        ) from None

    with _lock:
        _cache[cache_key] = (
            monotonic() + _CACHE_SECONDS,
            deepcopy(result),
        )
        _cache.move_to_end(cache_key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)

    return result
