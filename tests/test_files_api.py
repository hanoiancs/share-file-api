from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from internal_static_files.models import FileShare, ShareMode, StoredFile, User


def test_get_file_content_redirects_missing_login_to_login_route(client: TestClient) -> None:
    response = client.get("/files/123/content", follow_redirects=False)

    assert response.status_code in {302, 307}
    redirect = urlparse(response.headers["location"])
    assert redirect.path == "/api/auth/google/login"
    assert parse_qs(redirect.query)["handle_url"] == [
        "http://testserver/api/files/123/content"
    ]


def test_upload_html_and_read_raw_content(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/files",
        headers=auth_headers,
        data={"title": "Report", "share_mode": "public"},
        files={"upload": ("report.html", b"<script>alert(1)</script>", "text/html")},
    )

    assert response.status_code == 201
    file_id = response.json()["id"]

    content = client.get(f"/files/{file_id}/content", headers=auth_headers)
    assert content.status_code == 200
    assert content.text == "<script>alert(1)</script>"
    assert content.headers["content-type"].startswith("text/html")


def test_upload_markdown_and_read_rendered_content(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/files",
        headers=auth_headers,
        data={"title": "Notes", "share_mode": "public"},
        files={"upload": ("notes.md", b"# Notes", "text/markdown")},
    )

    assert response.status_code == 201

    content = client.get(f"/files/{response.json()['id']}/content", headers=auth_headers)
    assert content.status_code == 200
    assert content.text.strip() == "<h1>Notes</h1>"


def test_list_files_defaults_to_25_records_per_page(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    owner = db_session.exec(select(User).where(User.email == "alice@example.com")).one()
    for index in range(30):
        db_session.add(
            StoredFile(
                owner_id=owner.id,
                title=f"File {index:02}",
                original_filename=f"file-{index:02}.md",
                storage_path=f"generated/file-{index:02}.md",
                content_type="markdown",
                share_mode=ShareMode.SPECIFIC_PEOPLE,
                size_bytes=8,
            )
        )
    db_session.commit()

    response = client.get("/files", headers=auth_headers)

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


def test_list_files_supports_page_and_per_page(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    owner = db_session.exec(select(User).where(User.email == "alice@example.com")).one()
    for index in range(30):
        db_session.add(
            StoredFile(
                owner_id=owner.id,
                title=f"File {index:02}",
                original_filename=f"file-{index:02}.md",
                storage_path=f"generated/file-{index:02}.md",
                content_type="markdown",
                share_mode=ShareMode.SPECIFIC_PEOPLE,
                size_bytes=8,
            )
        )
    db_session.commit()

    response = client.get("/files?page=2&per_page=10", headers=auth_headers)

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


def test_list_files_includes_owner_and_shares(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    created = client.post(
        "/files",
        headers=auth_headers,
        data={"title": "Shared", "share_mode": "specific_people"},
        files={"upload": ("shared.md", b"# Shared", "text/markdown")},
    )
    file_id = created.json()["id"]
    share = FileShare(file_id=file_id, recipient_email="reader@example.com")
    db_session.add(share)
    db_session.commit()
    db_session.refresh(share)

    response = client.get("/files", headers=auth_headers)

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["owner"] == {"id": 1, "display_name": "alice"}
    assert item["shares"] == [
        {
            "id": share.id,
            "file_id": file_id,
            "recipient_email": "reader@example.com",
        }
    ]


def test_upload_rejects_unsupported_extension(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/files",
        headers=auth_headers,
        data={"title": "Bad", "share_mode": "public"},
        files={"upload": ("bad.txt", b"bad", "text/plain")},
    )

    assert response.status_code == 400


def test_upload_rejects_oversized_file(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/files",
        headers=auth_headers,
        data={"title": "Big", "share_mode": "public"},
        files={"upload": ("big.md", b"1" * 33, "text/markdown")},
    )

    assert response.status_code == 413


def test_specific_people_share_allows_matching_email(
    client: TestClient,
    auth_headers: dict[str, str],
    token_for_email,
) -> None:
    created = client.post(
        "/files",
        headers=auth_headers,
        data={"title": "Private", "share_mode": "specific_people"},
        files={"upload": ("private.md", b"# Private", "text/markdown")},
    )
    file_id = created.json()["id"]

    share_response = client.put(
        f"/files/{file_id}/shares",
        headers=auth_headers,
        json={"recipient_emails": ["Reader@Other.com"]},
    )

    assert share_response.status_code == 200

    reader_headers = {"Authorization": f"Bearer {token_for_email('reader@other.com')}"}
    response = client.get(f"/files/{file_id}", headers=reader_headers)
    assert response.status_code == 200


def test_owner_replaces_existing_file_shares_without_duplicate_key_error(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    created = client.post(
        "/files",
        headers=auth_headers,
        data={"title": "Private", "share_mode": "specific_people"},
        files={"upload": ("private.md", b"# Private", "text/markdown")},
    )
    file_id = created.json()["id"]
    first = client.put(
        f"/files/{file_id}/shares",
        headers=auth_headers,
        json={"recipient_emails": ["reader@example.com"]},
    )

    second = client.put(
        f"/files/{file_id}/shares",
        headers=auth_headers,
        json={"recipient_emails": ["reader@example.com", "other@example.com"]},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["recipient_emails"] == [
        "other@example.com",
        "reader@example.com",
    ]


def test_internal_share_denies_different_domain(
    client: TestClient,
    auth_headers: dict[str, str],
    token_for_email,
) -> None:
    created = client.post(
        "/files",
        headers=auth_headers,
        data={"title": "Internal", "share_mode": "internal"},
        files={"upload": ("internal.md", b"# Internal", "text/markdown")},
    )

    other_headers = {"Authorization": f"Bearer {token_for_email('reader@other.com')}"}
    response = client.get(f"/files/{created.json()['id']}", headers=other_headers)

    assert response.status_code == 403


def test_owner_replaces_content_and_delete_removes_file(
    client: TestClient,
    auth_headers: dict[str, str],
    storage_dir: Path,
    db_session: Session,
) -> None:
    created = client.post(
        "/files",
        headers=auth_headers,
        data={"title": "Replace", "share_mode": "public"},
        files={"upload": ("replace.md", b"# Old", "text/markdown")},
    )
    file_id = created.json()["id"]
    old_path = db_session.get(StoredFile, file_id).storage_path
    assert Path(old_path).parent == Path("1")
    assert (storage_dir / old_path).exists()

    replaced = client.put(
        f"/files/{file_id}/content",
        headers=auth_headers,
        files={"upload": ("replace.html", b"<h1>New</h1>", "text/html")},
    )

    assert replaced.status_code == 200
    replaced_file = db_session.get(StoredFile, file_id)
    assert replaced_file.storage_path != old_path
    assert Path(replaced_file.storage_path).parent == Path("1")
    assert not (storage_dir / old_path).exists()
    assert (storage_dir / replaced_file.storage_path).exists()

    deleted = client.delete(f"/files/{file_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert not (storage_dir / replaced_file.storage_path).exists()
