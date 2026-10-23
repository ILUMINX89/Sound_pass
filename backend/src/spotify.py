import base64
import json
import time

from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.config import settings

_spotify_token = None
_spotify_token_expires_at = 0


def get_spotify_token():
    global _spotify_token
    global _spotify_token_expires_at

    # Reutilizar token mientras siga vigente
    if _spotify_token and time.time() < _spotify_token_expires_at:
        return _spotify_token

    if not settings.spotify_client_id or not settings.spotify_client_secret:
        print("ERROR: No están configuradas las credenciales de Spotify.")
        return None

    credentials = f"{settings.spotify_client_id}:" f"{settings.spotify_client_secret}"

    encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")

    data = urlencode({"grant_type": "client_credentials"}).encode("utf-8")

    request = Request(
        "https://accounts.spotify.com/api/token",
        data=data,
        headers={
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))

        _spotify_token = result.get("access_token")

        expires_in = result.get("expires_in", 3600)

        # Renovarlo un minuto antes de vencer
        _spotify_token_expires_at = time.time() + expires_in - 60

        print("Token de Spotify obtenido correctamente.")

        return _spotify_token

    except HTTPError as error:
        body = error.read().decode("utf-8", errors="ignore")

        print(f"Error obteniendo token de Spotify " f"HTTP {error.code}: {body}")

    except URLError as error:
        print("Error de conexión con Spotify:", error)

    except Exception as error:
        print("Error obteniendo token de Spotify:", error)

    return None


def get_artist_image(artist_name: str):
    token = get_spotify_token()

    if not token:
        return None

    # IMPORTANTE:
    # Client Credentials no tiene usuario/país asociado,
    # por eso especificamos Colombia.
    query = urlencode(
        {
            "q": artist_name,
            "type": "artist",
            "market": "CO",
            "limit": 5,
        }
    )

    url = "https://api.spotify.com/v1/search?" + query

    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=10) as response:

            result = json.loads(response.read().decode("utf-8"))

        artists = result.get("artists", {}).get("items", [])

        print(f"Spotify devolvió " f"{len(artists)} resultados " f"para {artist_name}")

        if not artists:
            print(f"No se encontró artista " f"para: {artist_name}")
            return None

        # Primero intentar encontrar coincidencia exacta
        artist = next(
            (
                item
                for item in artists
                if item.get("name", "").casefold() == artist_name.casefold()
            ),
            artists[0],
        )

        print(f"Artista seleccionado: " f"{artist.get('name')}")

        images = artist.get("images", [])

        if not images:
            print(
                f"Spotify encontró a " f"{artist_name}, pero no " f"devolvió imágenes."
            )
            return None

        image_url = images[0].get("url")

        print(f"Imagen Spotify encontrada " f"para {artist_name}: " f"{image_url}")

        return image_url

    except HTTPError as error:
        body = error.read().decode("utf-8", errors="ignore")

        print(f"Spotify HTTP {error.code} " f"buscando {artist_name}: " f"{body}")

    except URLError as error:
        print(f"Error de conexión buscando " f"{artist_name}: {error}")

    except Exception as error:
        print(f"Error buscando imagen de " f"{artist_name}: {error}")

    return None

class SpotifyArtistError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 503,
        retry_after: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after


def get_artist_player(artist_name: str, *, include_images: bool = False):
    import re
    import unicodedata

    def normalize(value: str):
        return " ".join(
            unicodedata.normalize("NFKC", value).casefold().split()
        )

    if (
        not settings.spotify_client_id.strip()
        or not settings.spotify_client_secret.strip()
    ):
        raise SpotifyArtistError(
            "not_configured",
            "La integración con Spotify no está configurada.",
        )

    name = artist_name.strip()

    if not name:
        return {
            "status": "not_found",
            "artist": None,
            "message": "El concierto no tiene un artista registrado.",
        }

    token = get_spotify_token()

    if not token:
        raise SpotifyArtistError(
            "authentication_failed",
            "No fue posible obtener acceso a Spotify.",
        )

    query = urlencode({
        "q": name,
        "type": "artist",
        "market": "CO",
        "limit": 10,
    })

    request = Request(
        "https://api.spotify.com/v1/search?" + query,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))

    except HTTPError as error:
        if error.code == 429:
            retry_after = error.headers.get("Retry-After", "60")

            if not retry_after.isdigit():
                retry_after = "60"

            raise SpotifyArtistError(
                "rate_limited",
                "Spotify limitó temporalmente las consultas.",
                retry_after=retry_after,
            ) from None

        if error.code in (401, 403):
            raise SpotifyArtistError(
                "access_denied",
                "Spotify rechazó el acceso. Revisa la configuración "
                "y los permisos de la aplicación.",
            ) from None

        raise SpotifyArtistError(
            "spotify_unavailable",
            "Spotify no está disponible temporalmente.",
        ) from None

    except (URLError, TimeoutError, OSError):
        raise SpotifyArtistError(
            "spotify_unavailable",
            "No fue posible conectar con Spotify.",
        ) from None

    except (ValueError, UnicodeError):
        raise SpotifyArtistError(
            "invalid_response",
            "Spotify devolvió una respuesta inválida.",
            status_code=502,
        ) from None

    try:
        artists = result["artists"]["items"]

        if not isinstance(artists, list):
            raise ValueError()

        matches = {}

        for artist in artists:
            if (
                not isinstance(artist, dict)
                or not isinstance(artist.get("name"), str)
                or not isinstance(artist.get("id"), str)
                or not re.fullmatch(
                    r"[A-Za-z0-9]{22}", artist["id"]
                )
            ):
                raise ValueError()

            if normalize(artist["name"]) == normalize(name):
                matches[artist["id"]] = artist

    except (KeyError, TypeError, ValueError):
        raise SpotifyArtistError(
            "invalid_response",
            "Spotify devolvió información de artistas inválida.",
            status_code=502,
        ) from None

    if not matches:
        return {
            "status": "not_found",
            "artist": None,
            "message": "No se encontró una coincidencia exacta "
            "del artista en Spotify.",
        }

    if len(matches) > 1:
        return {
            "status": "ambiguous",
            "artist": None,
            "message": "Hay varios artistas con ese nombre en Spotify.",
        }

    artist = next(iter(matches.values()))
    artist_id = artist["id"]

    if include_images:
        from urllib.parse import urlsplit

        raw_images = artist.get("images", [])

        if not isinstance(raw_images, list):
            raise SpotifyArtistError(
                "invalid_response",
                "Spotify devolvió una lista de imágenes inválida.",
                status_code=502,
            )

        images = []
        seen_urls = set()

        def valid_dimension(value):
            if type(value) is int and value > 0:
                return value
            return None

        for item in raw_images:
            if not isinstance(item, dict):
                continue

            image_url = item.get("url")

            if not isinstance(image_url, str):
                continue

            image_url = image_url.strip()

            try:
                parsed = urlsplit(image_url)
                valid_url = (
                    parsed.scheme == "https"
                    and bool(parsed.hostname)
                    and parsed.username is None
                    and parsed.password is None
                )
            except ValueError:
                valid_url = False

            if not valid_url or image_url in seen_urls:
                continue

            seen_urls.add(image_url)
            images.append({
                "url": image_url,
                "width": valid_dimension(item.get("width")),
                "height": valid_dimension(item.get("height")),
            })

        return {
            "status": "ok" if images else "no_images",
            "artist": {
                "id": artist_id,
                "name": artist["name"],
                "spotify_url": (
                    f"https://open.spotify.com/artist/{artist_id}"
                ),
            },
            "images": images,
            "message": (
                None if images
                else "El artista no tiene imágenes disponibles en Spotify."
            ),
        }

    return {
        "status": "ok",
        "artist": {
            "id": artist_id,
            "name": artist["name"],
            "spotify_url": (
                f"https://open.spotify.com/artist/{artist_id}"
            ),
            "embed_url": (
                f"https://open.spotify.com/embed/artist/{artist_id}"
            ),
        },
        "message": None,
    }


def get_artist_gallery(artist_name: str):
    result = get_artist_player(artist_name, include_images=True)

    return {
        **result,
        "images": result.get("images", []),
    }
