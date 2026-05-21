from internal_static_files import models as _models
from internal_static_files.config import Settings
from internal_static_files.database import metadata

_ = _models

target_metadata = metadata


def get_alembic_database_url() -> str:
    return Settings().database_url
