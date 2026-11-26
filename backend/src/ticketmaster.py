"""Consulta informativa de próximos conciertos en Ticketmaster."""

import json
import re
import unicodedata
from math import isfinite
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from threading import Lock
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.config import settings
from src.seatgeek import find_price


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
_request_lock = Lock()
_next_request = 0.0


def _normalize(value):
    text = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in text if c.isalnum())


def _request(resource, params):
    global _next_request

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
    # Leave headroom under Discovery's five requests per second.
    with _request_lock:
        delay = _next_request - monotonic()
        if delay > 0:
            sleep(delay)
        _next_request = monotonic() + 0.27
    try:
        with urlopen(url, timeout=10) as response:
            data = json.load(response)
    except HTTPError as error:
        if error.code == 404 and resource.startswith("events/"):
            raise TicketmasterError(404, "event_not_found", "Concierto no encontrado en Ticketmaster.") from None
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


_SEATMAP_HOSTS = {"s1.ticketm.net", "media.ticketmaster.eu", "maps.ticketmaster.com"}


def _official_url(value, hosts=None):
    if not isinstance(value, str) or re.search(r"[\s\\\x00-\x1f]", value):
        return None
    try:
        url = urlsplit(value)
        if (
            url.scheme == "https" and url.hostname and url.port in (None, 443)
            and url.username is None and url.password is None
            and (hosts is None or url.hostname in hosts)
        ):
            return value
    except ValueError:
        pass
    return None


def _price_ranges(event):
    ranges = []
    for row in event.get("priceRanges") or []:
        if not isinstance(row, dict):
            continue
        currency = row.get("currency")
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            continue
        minimum, maximum = (
            value if type(value) in (float, int) and isfinite(value) and value >= 0 else None
            for value in (row.get("min"), row.get("max"))
        )
        if minimum is not None and maximum is not None and minimum > maximum:
            continue
        if minimum is not None or maximum is not None:
            ranges.append({"min": minimum, "max": maximum, "currency": currency})
    return ranges or None


def _spotify_id(attraction):
    ids = set()
    for link in (attraction.get("externalLinks") or {}).get("spotify") or []:
        url = _official_url(link.get("url"), {"open.spotify.com"})
        match = re.fullmatch(r"/artist/([A-Za-z0-9]{22})/?", urlsplit(url).path) if url else None
        if match:
            ids.add(match[1])
    return next(iter(ids)) if len(ids) == 1 else None


def _event_pages(attraction_id, keyword=None):
    params = {
        "attractionId": attraction_id,
        "startDateTime": (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "includeTBA": "no",
        "includeTBD": "no",
        "locale": "*",
        "sort": "date,asc",
        "size": 50,
    }
    if keyword:
        params["keyword"] = keyword
    # Discovery limits deep paging to the first 1,000 results of a query.
    for page in range(20):
        data = _request("events", {**params, "page": page})
        items = _items(data, "events")
        yield from items
        if not items or page + 1 >= (data.get("page") or {}).get("totalPages", 1):
            break


def _event_card(event, catalog):
    attractions = _items(event, "attractions")
    artist = next((item for item in attractions if item.get("id") in catalog
                   and catalog[item["id"]].allowed), None)
    if artist is None:
        return None
    origin = catalog[artist["id"]]
    venues = _items(event, "venues")
    venue = venues[0] if venues else event.get("place") or {}
    dates = event.get("dates") or {}
    start = dates.get("start") or {}
    classifications = event.get("classifications") or [{}]
    images = [item for item in event.get("images") or [] if _official_url(item.get("url"))]
    image = max(images, key=lambda item: item.get("width") or 0, default={})
    seatmap = (event.get("seatmap") or {}).get("staticUrl")
    prices = _price_ranges(event)
    return {
        "id": event["id"],
        "source": "ticketmaster",
        "artist": origin.name,
        "artist_id": artist["id"],
        "artist_origins": sorted(origin.countries),
        "artist_origin_source": origin.source,
        "tour_name": event.get("name"),
        "event_date": start.get("localDate"),
        "event_time": None if start.get("timeTBA") or start.get("noSpecificTime") else start.get("localTime"),
        "starts_at": None if start.get("timeTBA") or start.get("noSpecificTime") else start.get("dateTime"),
        "timezone": dates.get("timezone") or venue.get("timezone"),
        "status": (dates.get("status") or {}).get("code"),
        "venue": {
            "name": venue.get("name"),
            "city": (venue.get("city") or {}).get("name"),
            "address": ", ".join(value for value in ((venue.get("address") or {}).get(key)
                                 for key in ("line1", "line2")) if value) or None,
            "country_code": (venue.get("country") or {}).get("countryCode"),
        },
        "genre": (classifications[0].get("genre") or {}).get("name"),
        "image_url": image.get("url"),
        "price_ranges": prices,
        "price_source": "Ticketmaster" if prices else None,
        "seatmap_url": _official_url(seatmap, _SEATMAP_HOSTS),
        "url": _official_url(event.get("url")),
    }


_ADD_ON = re.compile(r"\b(vip|suites?|parking|estacionamiento|premium seats?|hospitality|meet[ -]and[ -]greet|add[ -]ons?|upgrades?|cannot split by day|2[ -]day tickets?)\b", re.IGNORECASE)


def _upcoming_start(event):
    dates = event.get("dates") or {}
    start = dates.get("start") or {}
    if (
        event.get("id") and start.get("localDate") and not start.get("dateTBA")
        and not start.get("dateTBD")
        and (dates.get("status") or {}).get("code") not in {"cancelled", "canceled", "postponed", "rescheduled"}
        and not _ADD_ON.search(event.get("name") or "")
    ):
        venues = _items(event, "venues")
        venue = venues[0] if venues else event.get("place") or {}
        zone_name = dates.get("timezone") or venue.get("timezone")
        try:
            zone = ZoneInfo(zone_name) if zone_name else timezone.utc
        except (ValueError, ZoneInfoNotFoundError):
            zone = timezone.utc
        now = datetime.now(zone)
        day = date.fromisoformat(start["localDate"])
        if start.get("timeTBA") or start.get("noSpecificTime") or not start.get("localTime"):
            return start if day >= now.date() else None
        instant = (datetime.fromisoformat(start["dateTime"]) if start.get("dateTime")
                   else datetime.combine(day, time.fromisoformat(start["localTime"])))
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=zone)
        return start if instant >= now else None
    return None


def get_event_detail(event_id, catalog, imported_origins=()):
    try:
        data = _event_detail(event_id)
        if imported_origins:
            attractions = _items(data, "attractions")
            evidence = {}
            for provider_id, origin in imported_origins:
                if provider_id:
                    continue
                matches = {item["id"] for item in attractions if item.get("id")
                           and _normalize(item.get("name") or "") == _normalize(origin.name)}
                if len(matches) == 1:
                    evidence.setdefault(matches.pop(), set()).add(origin)
            for artist_id, origins in evidence.items():
                if len(origins) == 1:
                    catalog.setdefault(artist_id, next(iter(origins)))
        card = _event_card(data, catalog)
        if card is None:
            raise TicketmasterError(404, "origin_not_eligible", "Origen del artista fuera del catálogo o sin verificar.")
        return card, data
    except (ValueError, TypeError, KeyError, AttributeError):
        raise _invalid_response() from None


def add_fallback_price(card):
    if card["price_ranges"]:
        return card
    price = find_price(card)
    ranges = _price_ranges({"priceRanges": [price]})
    if ranges:
        return {**card, "price_ranges": ranges, "price_source": "SeatGeek", "price_kind": "resale"}
    return card


def spotify_identity(event, artist_id, catalog):
    artist = next(item for item in _items(event, "attractions") if item.get("id") == artist_id)
    return catalog[artist_id].spotify_id or _spotify_id(artist)


def _invalid_response():
    return TicketmasterError(502, "ticketmaster_invalid_response", "Ticketmaster devolvió datos inesperados.")


def _cached(key, loader):
    if not settings.ticketmaster_api_key.strip():
        raise TicketmasterError(503, "ticketmaster_not_configured", "Ticketmaster no está configurado.")
    with _lock:
        cached = _cache.get(key)
        if cached and cached[0] > monotonic():
            _cache.move_to_end(key)
            return deepcopy(cached[1])

    try:
        result = loader()
    except (ValueError, TypeError, KeyError, AttributeError):
        raise _invalid_response() from None

    with _lock:
        _cache[key] = monotonic() + _CACHE_SECONDS, deepcopy(result)
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
    return result


def _event_detail(event_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", event_id):
        raise TicketmasterError(404, "event_not_found", "Concierto no encontrado en Ticketmaster.")

    def fetch():
        result = _request(f"events/{event_id}", {"locale": "*"})
        if result.get("id") != event_id:
            raise _invalid_response()
        return result

    return _cached(("event-detail", event_id), fetch)


def _lookup(artist, catalog, artist_id=None, exclude_event=None):
    result = {"artist": artist, "source": "ticketmaster", "status": "not_found",
              "events": [], "message": "No se encontró al artista en Ticketmaster."}
    if not artist_id:
        if not _normalize(artist):
            return result
        data = _request("attractions", {"keyword": artist, "classificationName": "music", "size": 50, "locale": "*"})
        matches = {item["id"] for item in _items(data, "attractions")
                   if item.get("id") and _normalize(item.get("name") or "") == _normalize(artist)}
        if not matches:
            return result
        if len(matches) > 1:
            return {**result, "status": "ambiguous", "message": "Se encontraron varios artistas con el mismo nombre."}
        artist_id = matches.pop()

    origin = catalog.get(artist_id)
    if not origin:
        return {**result, "status": "no_events", "message": "El origen del artista no está verificado."}
    if not origin.allowed:
        return {**result, "status": "no_events", "message": "El origen del artista está fuera del catálogo."}

    seen = {exclude_event}
    events = []
    for event in _event_pages(artist_id):
        start = _upcoming_start(event)
        event_id = event.get("id")
        if not start or event_id in seen or not any(item.get("id") == artist_id for item in _items(event, "attractions")):
            continue
        venues = _items(event, "venues")
        venue = venues[0] if venues else event.get("place") or {}
        events.append({
            "id": event_id,
            "date": start["localDate"],
            "time": None if start.get("timeTBA") or start.get("noSpecificTime") else start.get("localTime"),
            "starts_at": None if start.get("timeTBA") or start.get("noSpecificTime") else start.get("dateTime"),
            "timezone": (event.get("dates") or {}).get("timezone") or venue.get("timezone"),
            "city": (venue.get("city") or {}).get("name"),
            "country": (venue.get("country") or {}).get("name"),
            "venue": venue.get("name"),
        })
        seen.add(event_id)
    return {**result, "status": "ok" if events else "no_events", "events": events,
            "message": None if events else "No encontramos próximos conciertos en Ticketmaster."}


def get_artist_upcoming_events(artist, catalog, *, artist_id=None, exclude_event=None):
    key = ("upcoming", artist.casefold(), artist_id, exclude_event,
           tuple(sorted(catalog.items())), settings.ticketmaster_allowed_origins)
    return _cached(key, lambda: _lookup(artist.strip(), catalog, artist_id, exclude_event))


def get_public_concerts(keyword, catalog):
    keyword = keyword.strip()
    allowed = {provider_id: origin for provider_id, origin in catalog.items() if origin.allowed}
    key = ("catalog", keyword.casefold(), tuple(sorted(allowed.items())))

    def fetch(artist_id):
        # A configured artist search uses the stable ID even if the event title omits the name.
        search = None if _normalize(keyword) in _normalize(allowed[artist_id].name) else keyword
        events = {}
        for event in _event_pages(artist_id, search):
            if _upcoming_start(event) and event["id"] not in events:
                card = _event_card(event, allowed)
                if card:
                    events[event["id"]] = card
        return events

    def load():
        events = {}
        named = [artist_id for artist_id, origin in allowed.items()
                 if keyword and _normalize(keyword) == _normalize(origin.name)]
        with ThreadPoolExecutor(max_workers=4) as executor:
            for result in executor.map(fetch, named or allowed):
                events.update(result)
        return sorted(events.values(), key=lambda item: (
            item["event_date"], item["event_time"] or "", item["id"],
        ))

    return _cached(key, load)
