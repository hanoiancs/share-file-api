from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


class StorageError(Exception):
    pass


class UnsupportedFileTypeError(StorageError):
    pass


class UploadTooLargeError(StorageError):
    pass


@dataclass(frozen=True)
class StoredUpload:
    relative_path: str
    content_type: str
    size_bytes: int


class LocalFileStorage:
    def __init__(self, root: Path, max_upload_bytes: int) -> None:
        self.root: Path = Path(root)
        self.max_upload_bytes: int = max_upload_bytes

    def write_upload(
        self, user_id: int, original_filename: str, content: bytes
    ) -> StoredUpload:
        content_type, suffix = self._classify(original_filename)
        self._validate_size(content)
        relative_path = str(Path(str(user_id)) / f"{uuid4().hex}{suffix}")

        absolute_path = self.root / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        _ = absolute_path.write_bytes(content)

        return StoredUpload(
            relative_path=relative_path,
            content_type=content_type,
            size_bytes=len(content),
        )

    def replace_upload(
        self,
        previous_relative_path: str,
        user_id: int,
        original_filename: str,
        content: bytes,
    ) -> StoredUpload:
        new_upload = self.write_upload(user_id, original_filename, content)
        self.delete(previous_relative_path)
        return new_upload

    def read(self, relative_path: str) -> bytes:
        return self._safe_path(relative_path).read_bytes()

    def delete(self, relative_path: str) -> None:
        path = self._safe_path(relative_path)
        if path.exists():
            path.unlink()

    def _validate_size(self, content: bytes) -> None:
        if len(content) > self.max_upload_bytes:
            raise UploadTooLargeError("upload exceeds configured maximum size")

    def _classify(self, original_filename: str) -> tuple[str, str]:
        suffix = Path(original_filename).suffix.lower()
        if suffix in {".html", ".htm"}:
            return "html", suffix
        if suffix == ".md":
            return "markdown", suffix
        raise UnsupportedFileTypeError("unsupported file extension")

    def _safe_path(self, relative_path: str) -> Path:
        root = self.root.resolve()
        candidate = (root / relative_path).resolve()
        if not candidate.is_relative_to(root):
            raise StorageError("storage path escapes root")
        return candidate
