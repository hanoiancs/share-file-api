from app import models as _models
from app.config import Settings
from app.database import metadata

_ = _models

target_metadata = metadata


def get_alembic_database_url() -> str:
    return Settings().database_url
