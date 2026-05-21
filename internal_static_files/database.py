from collections.abc import Generator

from sqlmodel import SQLModel, Session, create_engine

from internal_static_files.config import get_settings


Base = SQLModel
metadata = SQLModel.metadata


def create_db_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def get_db() -> Generator[Session]:
    engine = create_db_engine(get_settings().database_url)
    with Session(engine) as session:
        yield session
