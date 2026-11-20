from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env file."""

    app_env: Literal["local", "test", "staging", "production"] = "local"

    database_url: str = (
        "postgresql+psycopg2://soundpass_user:soundpass_pass@127.0.0.1:5433/soundpass"
    )
    secret_key: str = "change-this-to-a-long-random-string"
    access_token_expire_minutes: int = 1440
    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5500,http://127.0.0.1:5500"
    )

    ticketmaster_api_key: str = ""
    ollama_base_url: str = ""
    ollama_model: str = "qwen2.5:1.5b"
    ollama_timeout_seconds: float = Field(default=55, gt=0, le=55)

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    @property
    def is_public(self) -> bool:
        return self.app_env in {"staging", "production"}

    @model_validator(mode="after")
    def validate_public_settings(self):
        if self.is_public:
            key = self.secret_key.strip()
            markers = ("change", "example", "replace", "your", "secret", "soundpass")
            if (len(key) < 32 or len(set(key)) < 12
                    or any(marker in key.lower() for marker in markers)):
                raise ValueError("SECRET_KEY debe ser aleatoria y tener al menos 32 caracteres")
            if self.database_url == type(self).model_fields["database_url"].default:
                raise ValueError("DATABASE_URL debe configurarse para el perfil público")
            for origin in self.cors_origins:
                parsed = urlsplit(origin)
                if (parsed.scheme != "https" or not parsed.hostname
                        or parsed.username or parsed.password
                        or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
                        or "*" in origin):
                    raise ValueError("ALLOWED_ORIGINS debe contener orígenes HTTPS explícitos")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
