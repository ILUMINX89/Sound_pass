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
