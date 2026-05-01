from functools import lru_cache
from pathlib import Path

from pydantic import AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "orbidi-fastapi-base"
    environment: str = "dev"
    secret_key: str  # Required – no default, must be set via env var

    base_url: str = "http://localhost:8000"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: AnyUrl = "http://localhost:8000/auth/callback"

    data_dir: Path = Path("data")

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
