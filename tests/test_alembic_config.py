from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from internal_static_files.database import metadata
from internal_static_files.migrations import get_alembic_database_url, target_metadata


def test_alembic_uses_sqlmodel_metadata() -> None:
    assert target_metadata is metadata


def test_alembic_database_url_loads_from_env_file(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/from_env\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert get_alembic_database_url() == "postgresql+psycopg://user:pass@localhost:5432/from_env"


def test_alembic_ini_points_to_env_py() -> None:
    config = Config("alembic.ini")

    assert config.get_main_option("script_location") == "alembic"


def test_alembic_upgrade_head_creates_current_schema(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "app.db"
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"DATABASE_URL=sqlite+pysqlite:///{database_path}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    project_root = Path(__file__).resolve().parents[1]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "alembic"))
    command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite+pysqlite:///{database_path}"))
    assert {"users", "user_auths", "files", "file_shares"}.issubset(inspector.get_table_names())
