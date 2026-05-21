from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime, String, Text, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class ShareMode(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SPECIFIC_PEOPLE = "specific_people"


class ContentType(StrEnum):
    HTML = "html"
    MARKDOWN = "markdown"


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def split_email_domain(email: str) -> str:
    normalized = normalize_email(email)
    if "@" not in normalized:
        raise ValueError("email must contain a domain")
    return normalized.rsplit("@", 1)[1]


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    google_sub: str = Field(index=True, unique=True, max_length=255)
    email: str = Field(index=True, unique=True, max_length=320)
    email_domain: str = Field(index=True, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False),
    )
    last_login_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    files: list["StoredFile"] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class StoredFile(SQLModel, table=True):
    __tablename__ = "files"

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="users.id", index=True)
    title: str = Field(max_length=255)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    original_filename: str = Field(max_length=255)
    storage_path: str = Field(unique=True, max_length=500)
    content_type: str = Field(max_length=32)
    share_mode: ShareMode = Field(
        default=ShareMode.PUBLIC,
        sa_column=Column(String(32), nullable=False),
    )
    size_bytes: int
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False),
    )

    owner: User = Relationship(back_populates="files")
    shares: list["FileShare"] = Relationship(
        back_populates="file",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class FileShare(SQLModel, table=True):
    __tablename__ = "file_shares"
    __table_args__ = (UniqueConstraint("file_id", "recipient_email"),)

    id: int | None = Field(default=None, primary_key=True)
    file_id: int | None = Field(default=None, foreign_key="files.id", index=True)
    recipient_email: str = Field(index=True, max_length=320)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    file: StoredFile | None = Relationship(back_populates="shares")
