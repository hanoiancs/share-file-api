from sqlmodel import SQLModel

from internal_static_files.database import metadata
from internal_static_files.models import FileShare, StoredFile, User


def test_database_metadata_comes_from_sqlmodel() -> None:
    assert metadata is SQLModel.metadata


def test_persistent_models_are_sqlmodel_tables() -> None:
    assert issubclass(User, SQLModel)
    assert issubclass(StoredFile, SQLModel)
    assert issubclass(FileShare, SQLModel)

    assert User.__tablename__ == "users"
    assert StoredFile.__tablename__ == "files"
    assert FileShare.__tablename__ == "file_shares"
