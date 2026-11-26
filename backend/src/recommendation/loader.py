"""Load the versioned recommender artifacts, accepting only files whose hashes match the manifest."""

import hashlib
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.recommendation.engine import ArtifactError, Model, ProfileStore

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Service:
    model: Model
    store: ProfileStore


def load(directory=None):
    directory = Path(directory or ARTIFACTS)
    manifest = json.loads((directory / "manifest.json").read_bytes())
    blobs = {}
    for name in ("model.json", "artist_profiles.json"):
        data = (directory / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest["files"][name]:
            raise ArtifactError(f"{name} no coincide con el manifiesto")
        blobs[name] = data
    model = Model(json.loads(blobs["model.json"]))
    if model.profiles_sha256 != manifest["files"]["artist_profiles.json"]:
        raise ArtifactError("el modelo no corresponde a estos perfiles")
    model.verify()
    store = ProfileStore(json.loads(blobs["artist_profiles.json"]))
    return Service(model, store)


@lru_cache(maxsize=1)
def get_service():
    """None when the artifacts are missing or untrusted: callers fall back to the general catalog."""
    try:
        return load()
    except (OSError, ValueError, KeyError, TypeError) as error:
        log.warning("Recomendador no disponible: %s", error.__class__.__name__)
        return None
