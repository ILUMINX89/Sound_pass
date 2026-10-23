"""Consulta de biografías musicales en Wikipedia en español."""

import json
import re
import unicodedata
from collections import OrderedDict
from threading import Lock
from time import monotonic
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://es.wikipedia.org/w/api.php"
USER_AGENT = (
    "SoundPass/1.0 "
    "(https://github.com/ILUMINX89/Sound_pass; artist biographies)"
)
TIMEOUT_SECONDS = 8
CACHE_TTL_SECONDS = 600
CACHE_MAX_ENTRIES = 256

_cache = OrderedDict()
_cache_lock = Lock()

_MUSIC_PATTERN = re.compile(
    r"\b(cantante|cantautor|cantautora|rapero|rapera|"
    r"musico|musica|compositor|compositora|"
    r"banda|grupo musical|duo musical|"
    r"disc jockey|dj)\b"
)


class WikipediaUnavailableError(Exception):
    """Wikipedia no respondió o devolvió una respuesta inválida."""


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(re.findall(r"\w+", value))


def _shorten(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= 600:
        return text

    shortened = text[:597].rsplit(" ", 1)[0]
    return shortened.rstrip(" ,;:.") + "..."


def _empty_result(status: str) -> dict:
    return {
        "status": status,
        "biography": None,
        "article_title": None,
        "article_url": None,
        "source": "Wikipedia",
    }


def _fetch_pages(titles: list[str]) -> list[dict]:
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "redirects": "1",
        "titles": "|".join(titles),
        "prop": "extracts|pageprops|info",
        "exintro": "1",
        "explaintext": "1",
        "exlimit": "max",
        "inprop": "url",
        "maxlag": "5",
    }
    request = Request(
        API_URL + "?" + urlencode(params),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(2_000_001)

        if len(raw) > 2_000_000:
            raise ValueError("Respuesta demasiado grande")

        data = json.loads(raw)
        if not isinstance(data, dict) or "error" in data:
            raise ValueError("Respuesta inválida de Wikipedia")

        pages = data["query"]["pages"]
        if not isinstance(pages, list):
            raise ValueError("Lista de páginas inválida")

        if any(not isinstance(page, dict) for page in pages):
            raise ValueError("Página inválida")

        return pages
    except (
        URLError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ) as exc:
        raise WikipediaUnavailableError(
            "No fue posible consultar Wikipedia"
        ) from exc


def _lookup(artist_name: str) -> dict:
    # Variantes explícitas: nunca elegimos el primer resultado
    # de una búsqueda general por similitud.
    titles = [
        artist_name,
        f"{artist_name} (cantante)",
        f"{artist_name} (banda)",
        f"{artist_name} (grupo musical)",
        f"{artist_name} (músico)",
        f"{artist_name} (rapero)",
    ]
    expected_name = _normalize(artist_name)
    candidates = {}
    uncertain = False

    for page in _fetch_pages(titles):
        if page.get("missing") or page.get("invalid"):
            continue

        if "disambiguation" in (page.get("pageprops") or {}):
            uncertain = True
            continue

        title = page.get("title")
        extract = page.get("extract")
        article_url = page.get("fullurl")

        if not all(
            isinstance(value, str) and value.strip()
            for value in (title, extract, article_url)
        ):
            continue

        base_title = re.sub(r"\s*\([^()]*\)\s*$", "", title)
        same_name = _normalize(base_title) == expected_name
        musical_intro = _MUSIC_PATTERN.search(
            _normalize(extract[:1200])
        )

        if not same_name or not musical_intro:
            uncertain = True
            continue

        if not article_url.startswith("https://es.wikipedia.org/wiki/"):
            raise WikipediaUnavailableError(
                "Wikipedia devolvió un enlace inesperado"
            )

        candidates[page["pageid"]] = {
            "status": "ok",
            "biography": _shorten(extract),
            "article_title": title,
            "article_url": article_url,
            "source": "Wikipedia",
        }

    if len(candidates) == 1:
        return next(iter(candidates.values()))

    if len(candidates) > 1 or uncertain:
        return _empty_result("ambiguous")

    return _empty_result("not_found")


def get_artist_bio(artist_name: str) -> dict:
    artist_name = " ".join((artist_name or "").split())

    if not artist_name:
        return _empty_result("not_found")

    # El separador | tiene significado especial en la API.
    if len(artist_name) > 200 or "|" in artist_name:
        return _empty_result("not_found")

    key = artist_name.casefold()
    now = monotonic()

    with _cache_lock:
        cached = _cache.get(key)
        if cached is not None:
            expires_at, result = cached
            if expires_at > now:
                _cache.move_to_end(key)
                return result.copy()
            del _cache[key]

    # Los fallos del proveedor no se guardan en caché.
    result = _lookup(artist_name)

    with _cache_lock:
        _cache[key] = (
            monotonic() + CACHE_TTL_SECONDS,
            result.copy(),
        )
        _cache.move_to_end(key)
        while len(_cache) > CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)

    return result
