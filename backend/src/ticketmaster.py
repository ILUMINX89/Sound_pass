"""Consulta informativa de próximos conciertos en Ticketmaster."""

import json
import unicodedata
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import urlopen

from src.config import settings


class TicketmasterError(Exception):
    def __init__(self, status_code, code, message, provider_status=None, retry_after=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.provider_status = provider_status
        self.retry_after = retry_after


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
            503, "ticketmaster_unavailable", message, error.code, error.headers.get("Retry-After")
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


def _lookup(artist, artist_id=None):
    result = {
        "artist": artist,
        "source": "ticketmaster",
        "status": "not_found",
        "events": [],
        "message": "No se encontró al artista en Ticketmaster.",
    }
    if not _normalize(artist):
        return result

    if artist_id is None:
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


def get_artist_upcoming_events(artist, attraction_id=None):
    if not settings.ticketmaster_api_key.strip():
        raise TicketmasterError(
            503,
            "ticketmaster_not_configured",
            "Ticketmaster no está configurado.",
        )

    artist = artist.strip()
    cache_key = (artist.casefold(), attraction_id)

    with _lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > monotonic():
            _cache.move_to_end(cache_key)
            return deepcopy(cached[1])

    try:
        result = _lookup(artist, attraction_id)
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


# The importer is deliberately serial and bounded; no requests occur while serving catalog reads.
from datetime import timedelta, date, time as local_time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from time import sleep

PURCHASE_HOSTS = {"ticketmaster.com", "ticketmaster.co", "ticketmaster.com.co", "ticketmaster.com.mx", "ticketmaster.es", "ticketmaster.co.uk", "ticketmaster.ca", "ticketmaster.ie", "ticketmaster.de", "ticketmaster.fr", "ticketmaster.nl", "ticketmaster.com.au", "ticketmaster.co.nz", "ticketmaster.cl"}

def purchase_url(value):
    if not isinstance(value, str):
        return None
    try:
        u = urlsplit(value)
        host = (u.hostname or "").lower()
        if u.scheme == "https" and not u.username and not u.password and u.port in (None, 443) and any(host == h or host.endswith("." + h) for h in PURCHASE_HOSTS):
            return value
    except ValueError:
        pass
    return None

def _catalog_request(params):
    # At most two attempts; a long Retry-After aborts the cycle instead of blocking indefinitely.
    for attempt in range(2):
        sleep(.25)
        try:
            return _request("events", params)
        except TicketmasterError as error:
            if error.provider_status != 429 or attempt:
                raise
            from email.utils import parsedate_to_datetime
            try:
                delay = float(error.retry_after or 1)
            except ValueError:
                try:
                    delay = (parsedate_to_datetime(error.retry_after) - datetime.now(timezone.utc)).total_seconds()
                except (ValueError, TypeError):
                    raise error from None
            if delay > 30:
                raise
            sleep(max(0, delay))

_detail_cache = OrderedDict()
_DETAIL_TTL = 6 * 60 * 60
_DETAIL_CACHE_MAX = 2048
_DETAIL_LIMIT = 20


def _has_venue_name(event):
    return any(isinstance(venue.get("name"), str) and venue["name"].strip()
               for venue in _items(event, "venues"))


def _enrich_events(events, detail_request, country):
    # Prioriza recintos; después consulta precios faltantes con el presupuesto restante.
    candidates = []
    for event in events:
        missing_venue = not _has_venue_name(event)
        missing_price = _minimum_price(event)[0] is None
        if missing_venue or missing_price:
            candidates.append((not missing_venue, event))
    candidates.sort(key=lambda candidate: candidate[0])

    calls = 0
    for _, event in candidates:
        event_id = event["id"]
        with _lock:
            cached = _detail_cache.get(event_id)
            if cached and cached[0] > monotonic():
                _detail_cache.move_to_end(event_id)
            else:
                cached = None
        if cached:
            detail = cached[1]
        else:
            if calls >= _DETAIL_LIMIT:
                continue
            calls += 1
            try:
                detail = detail_request(event_id)
            except TicketmasterError as error:
                # El detalle es opcional. Evita repetir una llamada por evento ante 429
                # o una caída, y conserva los datos de la búsqueda completa.
                if error.provider_status == 404:
                    detail = {}
                else:
                    break
            if not isinstance(detail, dict) or (detail and detail.get("id") != event_id):
                continue
            with _lock:
                _detail_cache[event_id] = (monotonic() + _DETAIL_TTL, detail)
                _detail_cache.move_to_end(event_id)
                while len(_detail_cache) > _DETAIL_CACHE_MAX:
                    _detail_cache.popitem(last=False)

        try:
            if not _has_venue_name(event) and _has_venue_name(detail):
                venues = [
                    venue for venue in _items(detail, "venues")
                    if not country or (venue.get("country") or {}).get("countryCode") in (None, country)
                ]
                if venues:
                    event["_embedded"] = {**event.get("_embedded", {}), "venues": venues}
        except (ValueError, AttributeError, TypeError):
            # Un detalle malformado no invalida la búsqueda ya completada.
            pass
        if _minimum_price(event)[0] is None and _minimum_price(detail)[0] is not None:
            event["priceRanges"] = detail["priceRanges"]
    return events


def _event_detail(event_id):
    sleep(.25)
    return _request("events/" + quote(event_id, safe=""), {})


def discover_events(country, start, end, request=None, keyword=None, *, detail_request=None):
    """Complete inclusive UTC windows, metadata pagination, ID deduplication, fail closed."""
    if not settings.ticketmaster_api_key.strip() and request is None:
        raise TicketmasterError(503, "ticketmaster_not_configured", "Ticketmaster no está configurado.")
    if detail_request is None and request is None:
        detail_request = _event_detail
    request = request or _catalog_request
    calls = 0
    def window(lo, hi):
        nonlocal calls
        def page(number):
            nonlocal calls
            calls += 1
            if calls > 250:
                raise ValueError("Catalog request budget exceeded")
            data = request({**({"countryCode": country} if country else {}), "classificationName": "music",
                "startDateTime": lo.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "endDateTime": hi.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "sort": "date,asc", "includeTBA": "no", "includeTBD": "no", "size": 200, "page": number,
                **({"keyword": keyword} if keyword else {})})
            meta = data.get("page")
            if not isinstance(meta, dict) or any(type(meta.get(k)) is not int or meta[k] < 0 for k in ("totalElements", "totalPages", "number", "size")):
                raise ValueError("Invalid pagination metadata")
            if meta["number"] != number or meta["size"] != 200:
                raise ValueError("Unexpected page")
            expected = (meta["totalElements"] + 199) // 200
            if meta["totalPages"] != expected:
                raise ValueError("Inconsistent pagination")
            return data, meta
        data, meta = page(0)
        if meta["totalElements"] > 1000:
            if (hi - lo).total_seconds() <= 1:
                raise ValueError("Unsplittable deep pagination")
            mid = lo + timedelta(seconds=int((hi-lo).total_seconds() // 2))
            return window(lo, mid) + window(mid, hi)
        items = _items(data, "events")
        for n in range(1, meta["totalPages"]):
            data, following = page(n)
            if following["totalElements"] != meta["totalElements"] or following["totalPages"] != meta["totalPages"]:
                raise ValueError("Catalog changed during pagination")
            items.extend(_items(data, "events"))
        if len(items) != meta["totalElements"] or len({e.get("id") for e in items}) != len(items) or any(not e.get("id") for e in items):
            raise ValueError("Incomplete event traversal")
        return items
    try:
        events = window(start.replace(microsecond=0), end.replace(microsecond=0))
        events = list({event["id"]: event for event in events}.values())
        return _enrich_events(events, detail_request, country) if detail_request else events
    except TicketmasterError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError):
        raise TicketmasterError(502, "ticketmaster_incomplete_catalog", "El recorrido del catálogo no fue completo o válido.") from None

def _minimum_price(event):
    prices = []
    ranges = event.get("priceRanges")
    for r in ranges if isinstance(ranges, list) else ():
        if not isinstance(r, dict):
            continue
        currency = r.get("currency")
        try:
            price = Decimal(str(r.get("min")))
            if isinstance(currency, str) and len(currency) == 3 and currency.isalpha() and price.is_finite() and 0 <= price < Decimal("10000000000000000"):
                prices.append((price, currency.upper()))
        except (InvalidOperation, TypeError):
            pass
    return min(prices) if prices and len({c for _, c in prices}) == 1 else (None, None)

def map_event(event, country):
    """None means intentionally omitted; malformed dates fail the complete cycle."""
    if not isinstance(event.get("id"), str) or not event.get("name"):
        raise ValueError("Invalid event identity")
    dates = event.get("dates") or {}
    start = dates.get("start") or {}
    status = (dates.get("status") or {}).get("code")
    if status in {"cancelled", "canceled", "postponed"} or start.get("dateTBA") or start.get("dateTBD"):
        return None
    if not start.get("localDate"):
        return None
    attractions = _items(event, "attractions")
    artists = {}
    for a in attractions:
        musical = any((c.get("segment") or {}).get("name", "").casefold() == "music" for c in a.get("classifications", []))
        if musical and isinstance(a.get("name"), str) and a["name"].strip():
            artists[a.get("id") or a["name"].casefold()] = a["name"].strip()
    if not artists:
        return None
    venues = _items(event, "venues")
    v = next((venue for venue in venues
              if isinstance(venue.get("name"), str) and venue["name"].strip()),
             venues[0] if venues else {})
    venue_country = (v.get("country") or {}).get("countryCode")
    if country and venue_country and venue_country != country:
        raise ValueError("Country mismatch")
    zone = dates.get("timezone") or v.get("timezone")
    if zone:
        ZoneInfo(zone)
    when = date.fromisoformat(start["localDate"])
    unknown = start.get("timeTBA") or start.get("noSpecificTime") or not start.get("localTime")
    hour = None if unknown else local_time.fromisoformat(start["localTime"])
    stamp = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00")) if start.get("dateTime") else None
    if stamp and stamp.tzinfo is None:
        raise ValueError("Naive source timestamp")
    if stamp:
        stamp = stamp.astimezone(timezone.utc)
    # A confirmed local date suffices for rescheduled events; unknown time remains null.
    price, currency = _minimum_price(event)
    images = [i.get("url") for i in event.get("images", []) if isinstance(i.get("url"), str) and i["url"].startswith("https://") and len(i["url"]) <= 500]
    classifications = event.get("classifications") or []
    genre = next(((c.get("genre") or {}).get("name") for c in classifications if (c.get("genre") or {}).get("name")), "Desconocido")
    return dict(external_id=event["id"], artist_provenance=json.dumps([{ "ticketmaster_id": a.get("id"), "name": a.get("name") } for a in attractions if a.get("id") in artists]), artist=", ".join(artists.values()), tour_name=event["name"],
        genre=genre[:50], event_date=when, event_time=hour, starts_at=stamp, timezone=zone,
        official_url=purchase_url(event.get("url")), provider_price=price, currency=currency,
        image_url=images[0] if images else None, country_code=venue_country or country,
        venue=dict(external_id=v.get("id"), name=(v.get("name") or "Recinto desconocido")[:150],
                   city=((v.get("city") or {}).get("name") or "Ciudad desconocida")[:100],
                   address=((v.get("address") or {}).get("line1") or "")[:255] or None))
