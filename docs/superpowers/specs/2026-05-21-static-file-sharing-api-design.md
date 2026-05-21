# Static File Sharing API Design

## Summary

Build an API-only FastAPI service for authenticated Google users to upload, manage, and share HTML or Markdown files. PostgreSQL stores users, file metadata, and share records. File bodies are stored in a configured local static storage directory and are never served directly without API authorization checks.

This first version has no browser UI. Clients authenticate through Google OAuth, receive an API-issued JWT, and use that JWT as a bearer token for protected endpoints.

## Goals

- Support uploads for `.html`, `.htm`, and `.md` files.
- Store user records and file metadata in PostgreSQL.
- Store uploaded file bodies in a local static folder.
- Authenticate users through Google OAuth.
- Issue API JWTs after successful Google login.
- Require authentication for all file read and write operations.
- Support three share modes:
  - `public`: any authenticated Google user can read.
  - `internal`: authenticated users whose email domain matches the owner email domain can read.
  - `specific_people`: authenticated users whose normalized email appears in the file share list can read.
- Allow sharing by recipient email before the recipient first logs in.
- Allow owners to replace uploaded content in place.
- Render Markdown to HTML when content is read.
- Preserve and serve raw HTML as uploaded.

## Non-Goals

- Anonymous public access.
- Server-rendered upload or management pages.
- File version history.
- Email invitation delivery.
- Object storage integration in the first implementation.
- HTML sanitization for uploaded HTML files.

## Architecture

The service will be split into focused modules:

- `auth`: Google OAuth login and callback, user upsert, API JWT issuing, and JWT verification.
- `users`: persisted user model and current-user lookup.
- `files`: upload, metadata update, content replacement, listing, and deletion.
- `sharing`: access policy checks for owner, public, internal, and specific-people reads.
- `storage`: local filesystem reads and writes under the configured static storage directory.
- `markdown`: Markdown-to-HTML rendering on read.

Stored files must only be read through authorized API endpoints. The local static directory should not be exposed through a public static mount, because access control depends on database metadata and the requesting user.

## Authentication

The API will use Google OAuth as the identity provider.

1. A client starts login through `GET /auth/google/login`, which redirects to the Google consent URL.
2. Google redirects to `GET /auth/google/callback`.
3. The callback validates the OAuth response, fetches or verifies the Google identity, and upserts the local user.
4. The API returns a JSON response containing its own JWT with at least the local user id and expiration.
5. Protected endpoints require `Authorization: Bearer <api_jwt>`.

The local user stores the Google subject, email, email domain, display name, avatar URL, timestamps, and last login timestamp. Email comparisons should use normalized lowercase email addresses. The email domain is extracted from the authenticated Google email.

## Data Model

### `users`

- `id`: primary key.
- `google_sub`: unique Google subject identifier.
- `email`: unique normalized email.
- `email_domain`: normalized domain from the email.
- `display_name`: optional Google profile display name.
- `avatar_url`: optional Google profile image URL.
- `created_at`: creation timestamp.
- `updated_at`: update timestamp.
- `last_login_at`: most recent successful login timestamp.

### `files`

- `id`: primary key.
- `owner_id`: foreign key to `users.id`.
- `title`: display title.
- `description`: optional description.
- `original_filename`: original client filename for display and audit.
- `storage_path`: relative storage path under the configured static storage directory.
- `content_type`: `html` or `markdown`.
- `share_mode`: `public`, `internal`, or `specific_people`.
- `size_bytes`: stored content size.
- `created_at`: creation timestamp.
- `updated_at`: update timestamp.

### `file_shares`

- `id`: primary key.
- `file_id`: foreign key to `files.id`.
- `recipient_email`: normalized email allowed to read when `share_mode` is `specific_people`.
- `created_at`: creation timestamp.

Recommended constraints:

- Unique `users.google_sub`.
- Unique `users.email`.
- Unique pair of `file_shares.file_id` and `file_shares.recipient_email`.
- Enumerated or checked values for `files.content_type` and `files.share_mode`.

## Access Rules

Owners can read, update, replace content, update sharing, and delete their files.

Non-owner read access is granted when one of these conditions is true:

- `share_mode = public`: requester is authenticated.
- `share_mode = internal`: requester is authenticated and `requester.email_domain == owner.email_domain`.
- `share_mode = specific_people`: requester is authenticated and `requester.email` matches a row in `file_shares`.

All file content endpoints require a valid API JWT. The first version does not support anonymous link sharing.

## API Surface

### Auth

- `GET /auth/google/login`: start Google OAuth by redirecting to the Google consent URL.
- `GET /auth/google/callback`: complete OAuth, upsert user, and return a JSON response containing an API JWT.
- `GET /me`: return the current authenticated user.

### Files

- `POST /files`: upload `.html`, `.htm`, or `.md` content with title, optional description, and share mode.
- `GET /files`: list files owned by the current user and files shared with the current user.
- `GET /files/{file_id}`: return file metadata if the current user can access it.
- `GET /files/{file_id}/content`: authorize, then return raw HTML or Markdown rendered to HTML.
- `PUT /files/{file_id}`: update owner-controlled metadata and share mode.
- `PUT /files/{file_id}/content`: replace stored content in place.
- `PUT /files/{file_id}/shares`: replace the specific-people recipient email list.
- `DELETE /files/{file_id}`: delete metadata, share rows, and the stored file.

## File Handling

Uploads accept only `.html`, `.htm`, and `.md` extensions. The API should also enforce a configured maximum upload size.

Stored filenames must be generated by the service, such as from a file id or UUID. The service must not trust the uploaded filename for storage paths. `original_filename` is retained only as metadata.

Replacing content updates the existing `files` record and writes a new generated storage path, then deletes the previous stored file after the database update succeeds. The file id and metadata are preserved. Regenerating the storage path on every replacement avoids stale extensions and partial overwrite behavior.

Markdown files are rendered to HTML when read through `GET /files/{file_id}/content`. HTML files are returned raw, unchanged from the uploaded content.

## Security Notes

Raw HTML is allowed by product requirement. This means a shared HTML file can execute scripts in the viewer's browser if the client renders it directly. The API should make this behavior explicit in documentation and should not expose raw HTML to anonymous users.

The local static folder must not be mounted as publicly browsable static content. All reads must pass through the authorization layer.

The service should:

- Normalize and validate emails.
- Generate safe storage paths.
- Enforce upload size limits.
- Avoid returning local filesystem paths in API responses.
- Use short-lived API JWTs with a server-side signing secret.
- Use environment variables for OAuth client configuration, JWT settings, database URL, storage directory, and upload size limits.

## Error Handling

- `400 Bad Request`: invalid share mode, unsupported extension, malformed recipient email, invalid metadata, or invalid upload.
- `401 Unauthorized`: missing, expired, or invalid API JWT.
- `403 Forbidden`: authenticated user lacks access to an existing file.
- `404 Not Found`: file does not exist.
- `413 Payload Too Large`: uploaded content exceeds configured max size.
- `500 Internal Server Error`: unexpected storage, database, or rendering failure.

## Testing

Tests should cover:

- Google callback user upsert behavior through mocked Google identity data.
- JWT issuance and protected endpoint dependency behavior.
- Share access matrix for owner, public, internal, specific people, and unauthorized users.
- Upload validation for supported and unsupported extensions.
- Upload size limit behavior.
- Storage path generation and original filename preservation.
- In-place content replacement.
- Markdown rendering on read.
- Delete cleanup for database rows and stored file.

## Configuration

Expected environment settings:

- `DATABASE_URL`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `JWT_EXPIRES_MINUTES`
- `STATIC_FILES_DIR`
- `MAX_UPLOAD_BYTES`

## Open Decisions Resolved

- Internal corporate access is based on the file owner's email domain.
- Public files require authentication.
- Specific people can be shared by email before signup.
- HTML is stored and served raw.
- Markdown is rendered to HTML on read.
- File content is replaceable in place.
- The first version is API-only.
- The API issues its own JWT after Google OAuth.
