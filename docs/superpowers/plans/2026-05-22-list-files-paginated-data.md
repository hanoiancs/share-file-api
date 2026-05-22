# List Files Paginated Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change `GET /files` from a bare list response to a pagination envelope with items and page metadata.

**Architecture:** Add a response schema in `schemas.py`, then update `list_files` to reuse one visibility filter for a count query and a paged item query. Keep the existing `page` and `per_page` query parameters, default `per_page` to 25, and preserve deterministic ordering by `StoredFile.id`.

**Tech Stack:** FastAPI, SQLModel, Pydantic, pytest.

---

### Task 1: Pagination Envelope Schema and Endpoint

**Files:**
- Modify: `internal_static_files/schemas.py`
- Modify: `internal_static_files/files.py`
- Test: `tests/test_files_api.py`

- [ ] **Step 1: Write failing tests**

Update `tests/test_files_api.py` pagination assertions so list responses are objects:

```python
assert response.status_code == 200
payload = response.json()
assert payload["page"] == 1
assert payload["per_page"] == 25
assert payload["total"] == 30
assert payload["total_pages"] == 2
files = payload["items"]
assert len(files) == 25
assert files[0]["title"] == "File 00"
assert files[-1]["title"] == "File 24"
```

For explicit pagination:

```python
assert response.status_code == 200
payload = response.json()
assert payload["page"] == 2
assert payload["per_page"] == 10
assert payload["total"] == 30
assert payload["total_pages"] == 3
files = payload["items"]
assert len(files) == 10
assert files[0]["title"] == "File 10"
assert files[-1]["title"] == "File 19"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_files_api.py::test_list_files_defaults_to_25_records_per_page tests/test_files_api.py::test_list_files_supports_page_and_per_page
```

Expected: FAIL because the endpoint currently returns a JSON list, not an object with `items`, `total`, and `total_pages`.

- [ ] **Step 3: Add response schema**

In `internal_static_files/schemas.py`, add:

```python
class PaginatedFilesResponse(BaseModel):
    items: list[FileMetadataResponse]
    page: int
    per_page: int
    total: int
    total_pages: int
```

- [ ] **Step 4: Update endpoint implementation**

In `internal_static_files/files.py`:

```python
from math import ceil

from sqlalchemy import func, or_
```

Import `PaginatedFilesResponse`, change `list_files` response model to it, build `visibility_filter`, run a count query, run the existing paged item query, and return:

```python
return PaginatedFilesResponse(
    items=list(candidates),
    page=page,
    per_page=per_page,
    total=total,
    total_pages=ceil(total / per_page) if total else 0,
)
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/test_files_api.py::test_list_files_defaults_to_25_records_per_page tests/test_files_api.py::test_list_files_supports_page_and_per_page
```

Expected: PASS.

- [ ] **Step 6: Run full suite**

Run:

```bash
uv run pytest
```

Expected: PASS.
