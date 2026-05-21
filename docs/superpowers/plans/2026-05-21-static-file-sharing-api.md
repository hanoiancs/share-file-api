# Static File Sharing API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved API-only FastAPI service for Google-authenticated users to upload, replace, list, and share HTML/Markdown files.

**Architecture:** Use a focused `internal_static_files` package with modules for configuration, database models/session, auth/JWT, sharing policies, local storage, Markdown rendering, and FastAPI routes. PostgreSQL is the production database target through SQLAlchemy, while tests use SQLite through dependency overrides.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2, Pydantic Settings, PyJWT, Authlib, markdown-it-py, pytest, FastAPI TestClient.

---

## File Structure

- Create `internal_static_files/__init__.py`: package marker.
- Create `internal_static_files/config.py`: environment-backed settings.
- Create `internal_static_files/database.py`: SQLAlchemy engine/session and FastAPI DB dependency.
- Create `internal_static_files/models.py`: `User`, `StoredFile`, `FileShare`, and enums.
- Create `internal_static_files/schemas.py`: request/response models.
- Create `internal_static_files/auth.py`: Google OAuth URL/callback helpers, JWT creation, JWT verification, current-user dependency.
- Create `internal_static_files/storage.py`: safe local file writes, reads, replacements, and deletes.
- Create `internal_static_files/sharing.py`: access-control policy checks.
- Create `internal_static_files/markdown.py`: Markdown rendering.
- Create `internal_static_files/files.py`: file API router.
- Create `internal_static_files/app.py`: FastAPI app factory and router wiring.
- Modify `main.py`: expose `app` and keep a CLI entrypoint.
- Modify `pyproject.toml`: add runtime and test dependencies plus pytest configuration.
- Create `tests/conftest.py`: isolated app, database, settings, and auth overrides.
- Create `tests/test_auth.py`: JWT and mocked Google callback behavior.
- Create `tests/test_sharing.py`: access matrix.
- Create `tests/test_files_api.py`: upload, list, read, replace, validation, and delete behavior.

## Task 1: Dependencies And App Skeleton

**Files:**
- Modify: `pyproject.toml`
- Modify: `main.py`
- Create: `internal_static_files/__init__.py`
- Create: `internal_static_files/config.py`
- Create: `internal_static_files/database.py`
- Create: `internal_static_files/models.py`
- Create: `internal_static_files/app.py`
- Create: `tests/conftest.py`
- Create: `tests/test_app_skeleton.py`

- [ ] **Step 1: Write the failing app skeleton test**

Create `tests/test_app_skeleton.py`:

```python
from fastapi.testclient import TestClient


def test_health_check_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_app_skeleton.py -v`

Expected: FAIL because the test fixtures and app package do not exist.

- [ ] **Step 3: Add dependencies and minimal app skeleton**

Update `pyproject.toml` dependencies:

```toml
dependencies = [
    "authlib>=1.6.5",
    "fastapi[standard]>=0.136.1",
    "markdown-it-py>=4.2.0",
    "psycopg[binary]>=3.3.2",
    "pydantic-settings>=2.14.1",
    "pyjwt>=2.10.1",
    "sqlalchemy>=2.0.44",
]

[dependency-groups]
dev = [
    "pytest>=9.0.1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Create the minimal package, settings, database, models, app factory, test fixture, and `main.py` app export.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_app_skeleton.py -v`

Expected: PASS.

## Task 2: Auth And User Identity

**Files:**
- Modify: `internal_static_files/auth.py`
- Modify: `internal_static_files/app.py`
- Modify: `tests/conftest.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write failing JWT and current-user tests**

Cover:

```python
def test_me_requires_bearer_token(client):
    response = client.get("/me")
    assert response.status_code == 401


def test_me_returns_authenticated_user(client, user_token):
    response = client.get("/me", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth.py -v`

Expected: FAIL because auth helpers and `/me` are missing.

- [ ] **Step 3: Implement JWT creation, current-user dependency, and `/me`**

Add JWT encode/decode with `sub`, `exp`, and `iat`; normalize emails and domains when creating users in test fixtures; add `/me` route.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_auth.py -v`

Expected: PASS.

## Task 3: Sharing Policy

**Files:**
- Create: `internal_static_files/sharing.py`
- Create: `tests/test_sharing.py`

- [ ] **Step 1: Write failing access matrix tests**

Cover owner access, authenticated public access, internal same-domain access, specific-recipient access, and denied users.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sharing.py -v`

Expected: FAIL because sharing policy does not exist.

- [ ] **Step 3: Implement policy function**

Add `can_read_file(requester, stored_file) -> bool` using owner, public, internal, and specific-people rules from the design.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_sharing.py -v`

Expected: PASS.

## Task 4: Storage And Markdown

**Files:**
- Create: `internal_static_files/storage.py`
- Create: `internal_static_files/markdown.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Write failing storage and Markdown tests**

Cover extension validation, generated storage names, read/write, replacement path regeneration, delete behavior, and Markdown rendering.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_storage.py -v`

Expected: FAIL because storage and Markdown modules do not exist.

- [ ] **Step 3: Implement storage service and Markdown rendering**

Implement local filesystem storage under `STATIC_FILES_DIR`, extension/content-type detection, max upload size checks, safe generated filenames, replacement write-before-delete behavior, and Markdown rendering through `markdown-it-py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_storage.py -v`

Expected: PASS.

## Task 5: Files API

**Files:**
- Create: `internal_static_files/schemas.py`
- Create: `internal_static_files/files.py`
- Modify: `internal_static_files/app.py`
- Create: `tests/test_files_api.py`

- [ ] **Step 1: Write failing API tests**

Cover authenticated upload, unsupported extension `400`, oversized upload `413`, list owned/shared files, metadata read authorization, raw HTML content read, Markdown rendered content read, owner-only metadata updates, share-list replacement, content replacement, and delete cleanup.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_files_api.py -v`

Expected: FAIL because file schemas and router do not exist.

- [ ] **Step 3: Implement file schemas and router**

Implement `POST /files`, `GET /files`, `GET /files/{file_id}`, `GET /files/{file_id}/content`, `PUT /files/{file_id}`, `PUT /files/{file_id}/content`, `PUT /files/{file_id}/shares`, and `DELETE /files/{file_id}`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_files_api.py -v`

Expected: PASS.

## Task 6: Google OAuth Callback Surface

**Files:**
- Modify: `internal_static_files/auth.py`
- Modify: `internal_static_files/app.py`
- Modify: `tests/test_auth.py`

- [ ] **Step 1: Write failing mocked OAuth tests**

Cover `GET /auth/google/login` redirecting to Google and `GET /auth/google/callback` upserting a user from mocked Google identity data and returning an API access token.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth.py -v`

Expected: FAIL because OAuth routes are incomplete.

- [ ] **Step 3: Implement OAuth routes with injectable identity fetcher**

Use Authlib to build the login redirect URL. Keep the callback identity-fetching function injectable or monkeypatchable so tests do not call Google.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_auth.py -v`

Expected: PASS.

## Task 7: Full Verification

**Files:**
- Modify as needed only to fix failures from the verification run.

- [ ] **Step 1: Run all tests**

Run: `uv run pytest -v`

Expected: PASS.

- [ ] **Step 2: Run import check**

Run: `uv run python -c "from internal_static_files.app import create_app; app = create_app(); print(app.title)"`

Expected output includes `Internal Static Files API`.

## Self-Review

- Spec coverage: auth, users, Postgres-targeted metadata models, local storage, upload/replace/delete, public/internal/specific-people sharing, Markdown rendering, raw HTML serving, and API-only behavior are covered.
- Placeholder scan: this plan intentionally leaves implementation code to the TDD tasks, but each task has exact files, commands, expected failure/pass conditions, and behavior to implement.
- Type consistency: the plan consistently uses `User`, `StoredFile`, `FileShare`, `ShareMode`, and `ContentType`.
