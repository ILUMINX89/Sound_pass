"""Dynamic public artist registry with a verified inclusion for Don Omar."""
import json
import logging
from time import monotonic, sleep


import httpx
from src.config import settings
from src.ticketmaster import (
    _catalog_request, _enrich_events, _event_detail, _items, _normalize,
    discover_events, map_event,
)


def public_get(client, url, **kwargs):
    for attempt in range(2):
        try:
            response = client.get(url, **kwargs)
            if response.status_code not in (429, 502, 503, 504) or attempt:
                response.raise_for_status()
                return response
            delay = float(response.headers.get("Retry-After", 2))
            if delay > 10:
                response.raise_for_status()
            sleep(max(0, delay))
        except httpx.TimeoutException:
            if attempt:
                raise
            sleep(2)

ORIGINS = {"US": "Q30", "MX": "Q96", "CO": "Q739", "AR": "Q414", "PR": "Q1183"}
_cache = None

def _include_don_omar(candidates, origins):
    if "PR" not in origins:
        return
    # Verified Puerto Rican origin. The ranking is for discovery, not eligibility.
    artist = candidates.setdefault("Q310539", {
        "id": "Q310539", "origins": [], "name": "Don Omar",
        "names": ["Don Omar"],
        "source": "https://music.apple.com/cl/artist/don-omar/65630139?l=en",
    })
    if "PR" not in artist["origins"]:
        artist["origins"].append("PR")
    if "Don Omar" not in artist["names"]:
        artist["names"].append("Don Omar")


def artist_registry():
    global _cache
    signature = (settings.ticketmaster_artist_origins, settings.ticketmaster_artists_per_origin, settings.ticketmaster_artist_min_sitelinks)
    if _cache and _cache[0] == signature and _cache[1] > monotonic():
        return _cache[2]
    origins = list(dict.fromkeys(v.strip() for v in settings.ticketmaster_artist_origins.split(",")))
    if not origins or any(v not in ORIGINS for v in origins):
        raise ValueError("Unsupported artist origin")
    candidates = {}
    headers = {"User-Agent": "SoundPassCatalog/1.0 (https://github.com/ILUMINX89/Sound_pass)", "Accept": "application/sparql-results+json"}
    with httpx.Client(timeout=45, headers=headers, follow_redirects=True) as client:
        for origin in origins:
            entity = ORIGINS[origin]
            condition = f"?artist wdt:P27 wd:{entity}."
            query = f"""SELECT DISTINCT ?artist ?links WHERE {{
                VALUES ?occupation {{ wd:Q177220 wd:Q225226 wd:Q488205 }}
                ?artist wdt:P31 wd:Q5; wdt:P106 ?occupation; wikibase:sitelinks ?links.
                {condition}
                FILTER NOT EXISTS {{ ?artist wdt:P570 ?death. }}
                FILTER(?links >= {settings.ticketmaster_artist_min_sitelinks})
            }} ORDER BY DESC(?links) ?artist LIMIT {settings.ticketmaster_artists_per_origin}"""
            response = public_get(client, "https://query.wikidata.org/sparql", params={"query": query, "format": "json"})
            response.raise_for_status()
            rows = response.json()["results"]["bindings"]
            if not rows:
                raise ValueError("Artist origin registry unavailable")
            for row in rows:
                identity = row["artist"]["value"].rsplit("/", 1)[-1]
                candidate = candidates.setdefault(identity, {"id": identity, "origins": [], "sitelinks": int(row["links"]["value"])})
                candidate["origins"].append(origin)
            logging.getLogger(__name__).info("artist_registry origin=%s selected=%d", origin, len(rows))
            sleep(.25)
        # Fetch labels/aliases in batches, not one external request per event or artist.
        ids = list(candidates)
        for offset in range(0, len(ids), 50):
            response = public_get(client, "https://www.wikidata.org/w/api.php", params={"action": "wbgetentities", "format": "json", "ids": "|".join(ids[offset:offset+50]), "props": "labels", "languages": "en|es|mul"})
            response.raise_for_status()
            entities = response.json()["entities"]
            for identity in ids[offset:offset+50]:
                entity = entities[identity]
                labels = entity.get("labels", {})
                name = (labels.get("en") or labels.get("es") or labels.get("mul") or {}).get("value")
                if not name:
                    raise ValueError("Missing verified artist label")
                candidates[identity].update(name=name, names=list(dict.fromkeys([name] + [v["value"] for v in labels.values()] )), source="https://www.wikidata.org/wiki/" + identity)
    _include_don_omar(candidates, origins)
    registry = list(candidates.values())
    logging.getLogger(__name__).info("artist_registry verified=%d bad_bunny_selected=%s", len(registry), any(_normalize(a["name"]) == "badbunny" for a in registry))
    _cache = (signature, monotonic()+86400, registry)
    return registry

def discover_selected_artists(start, end):
    registry = artist_registry()
    by_name = {}
    for artist in registry:
        for name in artist["names"]:
            key = _normalize(name)
            # Ambiguous verified labels fail closed.
            if key in by_name and by_name[key] != artist:
                by_name[key] = None
            elif key not in by_name:
                by_name[key] = artist
    events = {}
    # Event-first Discovery search. Wikidata chooses scope; Ticketmaster owns event identity/date.
    calls = 0
    began = monotonic()
    def bounded_request(params):
        nonlocal calls
        calls += 1
        if calls > 100 or monotonic() - began > 600:
            raise ValueError("Global catalog request or time budget exceeded")
        return _catalog_request(params)
    for artist in registry:
        for event in discover_events(None, start, end, keyword=artist["name"], request=bounded_request):
            events[event["id"]] = event
    eligible = []
    provenance = {}
    for event in events.values():
        musical = [a for a in _items(event, "attractions") if any((c.get("segment") or {}).get("name", "").casefold() == "music" for c in a.get("classifications", []))]
        matches = [by_name.get(_normalize(a.get("name", ""))) for a in musical]
        # Every published musical act must have verified eligible origin; no inferred nationality.
        if not matches or any(a is None for a in matches):
            continue
        eligible.append(event)
        provenance[event["id"]] = [{**person, "ticketmaster_id": act.get("id")} for act, person in zip(musical, matches)]

    # The injected search callback disables per-search enrichment. Apply the
    # detail budget once to the deduplicated, eligible global events instead.
    mapped = []
    for event in _enrich_events(eligible, _event_detail, None):
        data = map_event(event, None)
        if data is None:
            continue
        data["catalog_scope"] = settings.catalog_key
        data["artist_provenance"] = json.dumps(provenance[event["id"]], ensure_ascii=False)
        mapped.append(data)
    return list(events.values()), mapped, len(registry)
