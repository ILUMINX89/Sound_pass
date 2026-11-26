"""Optional price lookup using an authorized SeatGeek developer account.

SeatGeek reports resale-marketplace prices, so callers must label them as resale.
"""

import re
from collections import OrderedDict
from copy import deepcopy
from datetime import date, timedelta
from threading import Lock
from time import monotonic
from unicodedata import normalize

import httpx

from src.config import settings

_cache = OrderedDict()
_lock = Lock()
_CACHE_SECONDS = 900
_CACHE_MAX = 128
# Same exclusions as the Ticketmaster catalog: add-ons are not the regular show.
_ADD_ON = re.compile(
    r"\b(vip|suites?|parking|estacionamiento|premium seats?|hospitality|meet[ -]and[ -]greet|"
    r"add[ -]ons?|upgrades?|cannot split by day|2[ -]day tickets?)\b", re.IGNORECASE)


def _name(value):
    return " ".join(normalize("NFKC", value or "").casefold().split())


def _matches(card, event):
    venue = event.get("venue") or {}
    local = event.get("datetime_local") or ""
    time = card.get("event_time")
    return (
        event.get("id")
        and event.get("type") == "concert"
        and not any(_ADD_ON.search(str(event.get(key) or "")) for key in ("title", "short_title"))
        and not event.get("date_tbd")
        and local[:10] == card["event_date"]
        and (not time or not event.get("time_tbd") and local[11:16] == time[:5])
        and _name(venue.get("name")) == _name(card["venue"]["name"])
        and _name(venue.get("city")) == _name(card["venue"]["city"])
        and any(_name(artist.get("name")) == _name(card["artist"]) for artist in event.get("performers", []))
    )


def find_price(card):
    """Price for one exact show. Results, including misses, are cached briefly."""
    venue = card.get("venue") or {}
    key = (_name(card.get("artist")), card.get("event_date"), card.get("event_time"),
           _name(venue.get("name")), _name(venue.get("city")))
    with _lock:
        cached = _cache.get(key)
        if cached and cached[0] > monotonic():
            _cache.move_to_end(key)
            return deepcopy(cached[1])
    result = _lookup(card)
    with _lock:
        _cache[key] = monotonic() + _CACHE_SECONDS, deepcopy(result)
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
    return result


def _lookup(card):
    client_id, secret = settings.seatgeek_client_id.strip(), settings.seatgeek_client_secret.strip()
    if (not client_id or not secret
            or not all(_name(value) for value in (card["artist"], card["venue"]["name"], card["venue"]["city"]))
            or not card["event_date"]):
        return None
    try:
        day = date.fromisoformat(card["event_date"])
        response = httpx.get(
            "https://api.seatgeek.com/2/events",
            auth=(client_id, secret),
            params={
                "q": card["artist"], "venue.city": card["venue"]["city"], "type": "concert",
                "datetime_local.gte": day.isoformat(),
                "datetime_local.lt": (day + timedelta(days=1)).isoformat(),
                "per_page": 100,
            },
            timeout=4,
            follow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
        events = payload["events"]
        if payload["meta"]["total"] > len(events):
            return None
        matches = {event["id"]: event for event in events if _matches(card, event)}
        if len(matches) != 1:
            return None
        event = next(iter(matches.values()))
        stats = event.get("stats") or {}
        return {
            "min": stats.get("lowest_price"), "max": stats.get("highest_price"),
            "currency": stats.get("currency") or event.get("currency"),
        }
    except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError):
        return None
