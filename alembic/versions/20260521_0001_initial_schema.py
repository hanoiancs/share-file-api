"""initial schema

Revision ID: 20260521_0001
Revises:
Create Date: 2026-05-21 00:00:00

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260521_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_domain", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_email_domain"), "users", ["email_domain"], unique=False)

    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("share_mode", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_path"),
    )
    op.create_index(op.f("ix_files_owner_id"), "files", ["owner_id"], unique=False)

    op.create_table(
        "user_auths",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("oauth_provider", sa.String(length=64), nullable=False),
        sa.Column("oauth_id", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "oauth_provider"),
    )
    op.create_index(op.f("ix_user_auths_oauth_id"), "user_auths", ["oauth_id"], unique=False)

    op.create_table(
        "file_shares",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=True),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id", "recipient_email"),
    )
    op.create_index(op.f("ix_file_shares_file_id"), "file_shares", ["file_id"], unique=False)
    op.create_index(op.f("ix_file_shares_recipient_email"), "file_shares", ["recipient_email"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_file_shares_recipient_email"), table_name="file_shares")
    op.drop_index(op.f("ix_file_shares_file_id"), table_name="file_shares")
    op.drop_table("file_shares")

    op.drop_index(op.f("ix_user_auths_oauth_id"), table_name="user_auths")
    op.drop_table("user_auths")

    op.drop_index(op.f("ix_files_owner_id"), table_name="files")
    op.drop_table("files")

    op.drop_index(op.f("ix_users_email_domain"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
