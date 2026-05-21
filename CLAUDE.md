# CLAUDE.md

## Project

This repository is for an API-only FastAPI service that lets authenticated Google users upload, manage, and share HTML or Markdown files.

The approved design spec is:

- `docs/superpowers/specs/2026-05-21-static-file-sharing-api-design.md`

Read that spec before making architecture, API, data model, auth, storage, or sharing changes.

## Current Stack

- Python 3.13
- FastAPI
- PostgreSQL
- SQLModel
- Alembic
- Google OAuth
- API-issued JWT bearer authentication
- Local filesystem storage for uploaded HTML/Markdown bodies

Use `uv` for dependency and environment workflows when possible, because the repo already contains `pyproject.toml` and `uv.lock`.

Use Alembic for database schema changes. Alembic loads `DATABASE_URL` through the same `.env`-backed settings as the application.

## Product Rules

- This is API-only. Do not add browser UI unless explicitly requested.
- All file read and write operations require authentication.
- Public sharing means any authenticated Google user can read. It does not mean anonymous access.
- Internal sharing means the requester email domain matches the file owner's email domain.
- Specific-people sharing is by normalized recipient email and can be configured before that recipient has logged in.
- Owners can replace file content in place.
- HTML uploads are intentionally preserved and served raw.
- Markdown uploads are rendered to HTML on read.
- File metadata and users belong in PostgreSQL.
- Uploaded file bodies belong in the configured local static storage directory.
- Do not expose the storage directory through an unauthenticated static mount.

## Implementation Guidelines

- Keep modules focused around `auth`, `users`, `files`, `sharing`, `storage`, and Markdown rendering.
- Enforce authorization before reading file bodies from storage.
- Normalize emails to lowercase before storing or comparing them.
- Generate storage paths server-side. Never trust uploaded filenames for filesystem paths.
- Keep original filenames only as metadata.
- Do not return local filesystem paths in API responses.
- Enforce supported extensions: `.html`, `.htm`, and `.md`.
- Enforce a configured maximum upload size.
- Store environment-specific settings in configuration, including:
  - `DATABASE_URL`
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GOOGLE_REDIRECT_URI`
  - `JWT_SECRET_KEY`
  - `JWT_ALGORITHM`
  - `JWT_EXPIRES_MINUTES`
  - `STATIC_FILES_DIR`
  - `MAX_UPLOAD_BYTES`

## Testing Expectations

Add or update tests when changing behavior. Cover at least:

- JWT-protected endpoint behavior
- Google OAuth callback user upsert with mocked Google identity data
- Access checks for owner, public, internal, specific-people, and denied users
- Upload extension and size validation
- Storage path generation
- Content replacement
- Markdown rendering
- Deleting database rows and stored files

## Security Notes

Raw HTML is allowed by requirement and carries XSS risk if clients render it directly. Do not silently sanitize raw HTML unless the product requirement changes.

Because sharing is metadata-driven, storage access must always go through the API authorization layer.

## Git Hygiene

- Do not revert user changes unless explicitly asked.
- Keep changes scoped to the requested task.
- Avoid unrelated refactors.
