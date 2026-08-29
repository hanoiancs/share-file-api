from pathlib import Path

import pytest

from app.markdown import render_markdown
from app.storage import LocalFileStorage, UnsupportedFileTypeError, UploadTooLargeError


def test_storage_writes_generated_path_and_preserves_content(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path, max_upload_bytes=1024)

    stored = storage.write_upload(
        user_id=42, original_filename="report.html", content=b"<h1>Hello</h1>"
    )

    assert stored.content_type == "html"
    assert stored.relative_path != "report.html"
    assert Path(stored.relative_path).parent == Path("42")
    assert storage.read(stored.relative_path) == b"<h1>Hello</h1>"


def test_storage_rejects_unsupported_extension(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path, max_upload_bytes=1024)

    with pytest.raises(UnsupportedFileTypeError):
        storage.write_upload(
            user_id=42, original_filename="report.txt", content=b"hello"
        )


def test_storage_rejects_oversized_upload(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path, max_upload_bytes=4)

    with pytest.raises(UploadTooLargeError):
        storage.write_upload(
            user_id=42, original_filename="report.md", content=b"hello"
        )


def test_storage_replacement_regenerates_path_and_deletes_previous(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path, max_upload_bytes=1024)
    first = storage.write_upload(
        user_id=42, original_filename="report.md", content=b"# Old"
    )

    second = storage.replace_upload(
        previous_relative_path=first.relative_path,
        user_id=42,
        original_filename="report.html",
        content=b"<h1>New</h1>",
    )

    assert second.relative_path != first.relative_path
    assert Path(second.relative_path).parent == Path("42")
    assert not (tmp_path / first.relative_path).exists()
    assert storage.read(second.relative_path) == b"<h1>New</h1>"


def test_markdown_renders_to_html() -> None:
    assert render_markdown("# Hello").strip() == "<h1>Hello</h1>"
