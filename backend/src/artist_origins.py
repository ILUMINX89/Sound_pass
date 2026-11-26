"""Artist provenance from the local importer and curated provider identities."""

import json
from dataclasses import dataclass

from sqlalchemy import func, literal_column, null

from src import models
from src.config import settings


@dataclass(frozen=True)
class ArtistOrigin:
    name: str
    countries: frozenset[str]
    source: str
    spotify_id: str | None = None

    @property
    def allowed(self):
        return bool(self.countries.intersection(settings.ticketmaster_allowed_origins))


# Discovery attraction K8vZ917bvf7 links to this Spotify artist profile.
CURATED = {
    "K8vZ917bvf7": ArtistOrigin(
        "Duki", frozenset({"AR"}), "https://www.ticketmaster.com/duki-tickets/artist/2627891",
        "1bAftSH8umNcGZ0uyV7LMg",
    ),
}


def concert_metadata(db, *extra_fields):
    # PostgreSQL installs predating the importer have no optional catalog columns.
    fields = ("source", "external_id", "artist_provenance", *extra_fields)
    if db.get_bind().dialect.name != "postgresql":
        return tuple(null().label(field) for field in fields)
    metadata = func.to_jsonb(literal_column("concerts"))
    return tuple(func.jsonb_extract_path_text(metadata, field).label(field) for field in fields)


def origin_evidence(value):
    try:
        entries = json.loads(value) if value else []
    except (TypeError, ValueError):
        return
    if not isinstance(entries, list):
        return
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name, source, origins = (entry.get(key) for key in ("name", "source", "origins"))
        if not entry.get("id") or not isinstance(name, str) or not isinstance(source, str):
            continue
        if not source.startswith("https://") or not isinstance(origins, list):
            continue
        countries = frozenset(code.upper() for code in origins if isinstance(code, str) and len(code) == 2)
        if countries:
            yield entry.get("ticketmaster_id"), ArtistOrigin(name, countries, source)


def artist_catalog(db):
    source, _, provenance = concert_metadata(db)
    rows = db.query(provenance).select_from(models.Concert).filter(source == "ticketmaster").distinct().all()
    catalog = {}
    for (value,) in rows:
        for provider_id, origin in origin_evidence(value):
            if isinstance(provider_id, str):
                catalog.setdefault(provider_id, set()).add(origin)
    # Conflicting countries for the same identity need human review.
    verified = {
        provider_id: next(iter(sorted(evidence, key=lambda item: (item.source, item.name))))
        for provider_id, evidence in catalog.items()
        if len({item.countries for item in evidence}) == 1
    }
    return {**verified, **CURATED}
