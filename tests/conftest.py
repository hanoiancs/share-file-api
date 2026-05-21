from collections.abc import Callable, Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from internal_static_files.app import create_app
from internal_static_files.auth import create_access_token
from internal_static_files.config import Settings, get_settings
from internal_static_files.database import Base, get_db
from internal_static_files.models import FileShare, ShareMode, StoredFile, User, UserAuth, normalize_email, split_email_domain


@pytest.fixture()
def storage_dir(tmp_path: Path) -> Path:
    return tmp_path / "static-files"


@pytest.fixture()
def settings(storage_dir: Path) -> Settings:
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        google_client_id="test-client-id",
        google_client_secret="test-client-secret",
        google_redirect_uri="http://testserver/auth/google/callback",
        jwt_secret_key="test-secret-key-with-at-least-32-bytes",
        static_files_dir=storage_dir,
        max_upload_bytes=32,
    )


@pytest.fixture()
def db_session(settings: Settings) -> Generator[Session]:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def app(settings: Settings, db_session: Session):
    app = create_app()

    def override_settings() -> Settings:
        return settings

    def override_db() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_db] = override_db
    return app


@pytest.fixture()
def client(app) -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def user_factory(db_session: Session) -> Callable[..., User]:
    def factory(email: str = "alice@example.com", oauth_id: str | None = None) -> User:
        normalized = normalize_email(email)
        user = User(
            email=normalized,
            email_domain=split_email_domain(normalized),
            display_name=normalized.split("@", 1)[0],
        )
        db_session.add(user)
        db_session.flush()
        db_session.add(
            UserAuth(
                user_id=user.id,
                oauth_provider="google",
                oauth_id=oauth_id or f"google-{normalized}",
            )
        )
        db_session.commit()
        db_session.refresh(user)
        return user

    return factory


@pytest.fixture()
def file_factory(db_session: Session) -> Callable[..., StoredFile]:
    def factory(owner: User, share_mode: ShareMode = ShareMode.PUBLIC) -> StoredFile:
        stored_file = StoredFile(
            owner_id=owner.id,
            title="Report",
            original_filename="report.md",
            storage_path="generated/report.md",
            content_type="markdown",
            share_mode=share_mode,
            size_bytes=8,
        )
        db_session.add(stored_file)
        db_session.commit()
        db_session.refresh(stored_file)
        return stored_file

    return factory


@pytest.fixture()
def share_factory(db_session: Session) -> Callable[[StoredFile, str], FileShare]:
    def factory(stored_file: StoredFile, email: str) -> FileShare:
        share = FileShare(file_id=stored_file.id, recipient_email=normalize_email(email))
        db_session.add(share)
        db_session.commit()
        db_session.refresh(share)
        return share

    return factory


@pytest.fixture()
def token_for_email(settings: Settings, user_factory: Callable[..., User]) -> Callable[[str], str]:
    def factory(email: str) -> str:
        user = user_factory(email=email)
        return create_access_token(user, settings)

    return factory


@pytest.fixture()
def user_token(token_for_email: Callable[[str], str]) -> str:
    return token_for_email("alice@example.com")


@pytest.fixture()
def auth_headers(user_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_token}"}
