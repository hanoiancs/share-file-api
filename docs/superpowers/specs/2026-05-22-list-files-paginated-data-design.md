# List Files Paginated Data Design

## Context

`GET /files` currently accepts `page` and `per_page` query parameters and applies `offset` and `limit`, defaulting to 25 records per page. The response body is still a bare list of file metadata records. Clients need paginated data, including metadata such as total count and total pages, to render page controls correctly.

## Decision

Change `GET /files` to return a pagination envelope instead of a bare list.

Request:

```http
GET /files?page=1&per_page=25
```

Response:

```json
{
  "items": [],
  "page": 1,
  "per_page": 25,
  "total": 0,
  "total_pages": 0
}
```

`items` contains the same file metadata objects currently returned by the endpoint.

## API Contract

- `page` is a one-based page number.
- `per_page` is the requested page size.
- `per_page` defaults to 25.
- `page` and `per_page` must be greater than or equal to 1.
- `total` is the count of files visible to the authenticated user under the same authorization rules as the item query.
- `total_pages` is `ceil(total / per_page)`.
- When `total` is 0, `total_pages` is 0.
- The endpoint keeps deterministic ordering by `StoredFile.id`.

## Implementation

Add `PaginatedFilesResponse` to `internal_static_files/schemas.py`:

```python
class PaginatedFilesResponse(BaseModel):
    items: list[FileMetadataResponse]
    page: int
    per_page: int
    total: int
    total_pages: int
```

Update `list_files` in `internal_static_files/files.py`:

- Change the response model to `PaginatedFilesResponse`.
- Build the existing visibility filter once and reuse it for both queries.
- Run a count query against the visible files to compute `total`.
- Run the item query with `order_by(StoredFile.id)`, `offset`, and `limit`.
- Return the envelope with the paged files and metadata.

The response shape change is intentionally breaking because clients need metadata in the body.

## Error Handling

FastAPI query validation will continue to reject invalid `page` or `per_page` values with `422 Unprocessable Entity`.

## Testing

Update file API tests to cover:

- Default pagination returns 25 items with `page=1`, `per_page=25`, `total`, and `total_pages`.
- Explicit pagination such as `page=2&per_page=10` returns the expected slice and metadata.
- Existing file list authorization behavior remains unchanged because both count and item queries use the same visibility filter.

## Scope

This design only changes `GET /files`. It does not add sorting options, filtering options, cursor pagination, or pagination headers.
