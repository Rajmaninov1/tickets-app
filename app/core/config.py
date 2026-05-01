import logging
from functools import lru_cache
from pathlib import Path

from pydantic import AnyUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def configure_logging(level_name: str) -> None:
    """Apply root logging configuration so app loggers respect LOG_LEVEL."""
    mapping = logging.getLevelNamesMapping()
    key = level_name.strip().upper()
    if key not in mapping:
        choices = ", ".join(sorted(mapping))
        raise ValueError(f"Invalid log level '{level_name}'. Expected one of: {choices}")

    logging.basicConfig(
        level=mapping[key],
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

    # When root is DEBUG, third-party HTTP stacks inherit DEBUG and flood logs (httpcore, etc.).
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.INFO)
    logging.getLogger("fastapi_sso").setLevel(logging.INFO)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "orbidi-fastapi-base"
    environment: str = "dev"
    secret_key: str  # Required – no default, must be set via env var
    log_level: str = "INFO"

    base_url: str = "http://localhost:8000"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def allow_all_origins_in_dev(cls, v: object, info: any) -> object:
        # If the environment is dev, we allow all origins
        # Note: In pydantic-settings, we might need to check the raw value or 'v'
        return v

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: AnyUrl = "http://localhost:8000/auth/callback"

    data_dir: Path = Path("data")

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> str:
        if isinstance(value, str):
            return value.strip().upper()
        raise TypeError("log_level must be a string")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        if value not in logging.getLevelNamesMapping():
            choices = ", ".join(sorted(logging.getLevelNamesMapping()))
            raise ValueError(f"Invalid log_level '{value}'. Expected one of: {choices}")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
