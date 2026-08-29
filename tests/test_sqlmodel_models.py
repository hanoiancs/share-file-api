from sqlmodel import SQLModel

from app.database import metadata
from app.models import FileShare, StoredFile, User, UserAuth


def test_database_metadata_comes_from_sqlmodel() -> None:
    assert metadata is SQLModel.metadata


def test_persistent_models_are_sqlmodel_tables() -> None:
    assert issubclass(User, SQLModel)
    assert issubclass(UserAuth, SQLModel)
    assert issubclass(StoredFile, SQLModel)
    assert issubclass(FileShare, SQLModel)

    assert User.__tablename__ == "users"
    assert UserAuth.__tablename__ == "user_auths"
    assert StoredFile.__tablename__ == "files"
    assert FileShare.__tablename__ == "file_shares"


def test_user_auths_store_oauth_identity_outside_users() -> None:
    user_columns = set(User.__table__.columns.keys())
    user_auth_columns = set(UserAuth.__table__.columns.keys())

    assert "google_sub" not in user_columns
    assert user_auth_columns == {"user_id", "oauth_provider", "oauth_id"}
