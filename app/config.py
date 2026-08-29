from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+pysqlite:///./internal_static_files.db"
    google_client_id: str = "change-me"
    google_client_secret: str = "change-me"
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    client_default_redirect_url: str = "http://localhost:3000/auth/complete"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60
    static_files_dir: Path = Path("statics")
    max_upload_bytes: int = 5 * 1024 * 1024
    allowed_users: list[str] = []

    model_config = SettingsConfigDict(env_file=".env.dev", extra="allow")


@lru_cache
def get_settings() -> Settings:
    return Settings()
