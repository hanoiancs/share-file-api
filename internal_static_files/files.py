from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from internal_static_files.auth import get_current_user
from internal_static_files.config import Settings, get_settings
from internal_static_files.database import get_db
from internal_static_files.markdown import render_markdown
from internal_static_files.models import (
    FileShare,
    ShareMode,
    StoredFile,
    User,
    normalize_email,
)
from internal_static_files.schemas import (
    FileMetadataResponse,
    FileUpdateRequest,
    ShareListRequest,
    ShareListResponse,
)
from internal_static_files.sharing import can_read_file
from internal_static_files.storage import (
    LocalFileStorage,
    UnsupportedFileTypeError,
    UploadTooLargeError,
)

router = APIRouter(prefix="/files", tags=["files"])


def get_storage(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LocalFileStorage:
    return LocalFileStorage(settings.static_files_dir, settings.max_upload_bytes)


def _get_file_or_404(db: Session, file_id: int) -> StoredFile:
    stored_file = db.exec(
        select(StoredFile)
        .where(StoredFile.id == file_id)
        .options(selectinload(StoredFile.owner), selectinload(StoredFile.shares))
    ).first()
    if stored_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="file not found"
        )
    return stored_file


def _require_read(user: User, stored_file: StoredFile) -> None:
    if not can_read_file(user, stored_file):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="access denied"
        )


def _require_owner(user: User, stored_file: StoredFile) -> None:
    if user.id != stored_file.owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="owner access required"
        )


async def _read_upload(upload: UploadFile) -> bytes:
    return await upload.read()


def _storage_error_to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, UnsupportedFileTypeError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, UploadTooLargeError):
        return HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="storage failure"
    )


@router.post(
    "", response_model=FileMetadataResponse, status_code=status.HTTP_201_CREATED
)
async def create_file(
    title: Annotated[str, Form(min_length=1, max_length=255)],
    share_mode: Annotated[ShareMode, Form()],
    upload: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[LocalFileStorage, Depends(get_storage)],
    description: Annotated[str | None, Form()] = None,
) -> StoredFile:
    content = await _read_upload(upload)
    try:
        stored_upload = storage.write_upload(upload.filename or "upload", content)
    except Exception as exc:
        raise _storage_error_to_http(exc) from exc
    stored_file = StoredFile(
        owner_id=current_user.id,
        title=title,
        description=description,
        original_filename=upload.filename or "upload",
        storage_path=stored_upload.relative_path,
        content_type=stored_upload.content_type,
        share_mode=share_mode,
        size_bytes=stored_upload.size_bytes,
    )
    db.add(stored_file)
    db.commit()
    db.refresh(stored_file)
    return stored_file


@router.get("", response_model=list[FileMetadataResponse])
def list_files(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[StoredFile]:
    candidates = db.exec(
        select(StoredFile)
        .join(User, StoredFile.owner_id == User.id)
        .outerjoin(FileShare, FileShare.file_id == StoredFile.id)
        .where(
            or_(
                StoredFile.owner_id == current_user.id,
                StoredFile.share_mode == ShareMode.PUBLIC,
                (StoredFile.share_mode == ShareMode.INTERNAL)
                & (User.email_domain == current_user.email_domain),
                (StoredFile.share_mode == ShareMode.SPECIFIC_PEOPLE)
                & (FileShare.recipient_email == normalize_email(current_user.email)),
            )
        )
        .options(selectinload(StoredFile.owner), selectinload(StoredFile.shares))
        .distinct()
    ).all()
    return list(candidates)


@router.get("/{file_id}", response_model=FileMetadataResponse)
def get_file(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StoredFile:
    stored_file = _get_file_or_404(db, file_id)
    _require_read(current_user, stored_file)
    return stored_file


@router.get("/{file_id}/content")
def get_file_content(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[LocalFileStorage, Depends(get_storage)],
) -> Response:
    stored_file = _get_file_or_404(db, file_id)
    _require_read(current_user, stored_file)
    content = storage.read(stored_file.storage_path)
    if stored_file.content_type == "markdown":
        return HTMLResponse(render_markdown(content.decode("utf-8")))
    return HTMLResponse(content.decode("utf-8"))


@router.put("/{file_id}", response_model=FileMetadataResponse)
def update_file(
    file_id: int,
    payload: FileUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StoredFile:
    stored_file = _get_file_or_404(db, file_id)
    _require_owner(current_user, stored_file)
    if payload.title is not None:
        stored_file.title = payload.title
    if payload.description is not None:
        stored_file.description = payload.description
    if payload.share_mode is not None:
        stored_file.share_mode = payload.share_mode
    db.commit()
    db.refresh(stored_file)
    return stored_file


@router.put("/{file_id}/content", response_model=FileMetadataResponse)
async def replace_file_content(
    file_id: int,
    upload: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[LocalFileStorage, Depends(get_storage)],
) -> StoredFile:
    stored_file = _get_file_or_404(db, file_id)
    _require_owner(current_user, stored_file)
    content = await _read_upload(upload)
    previous_path = stored_file.storage_path
    try:
        stored_upload = storage.replace_upload(
            previous_path, upload.filename or stored_file.original_filename, content
        )
    except Exception as exc:
        raise _storage_error_to_http(exc) from exc
    stored_file.original_filename = upload.filename or stored_file.original_filename
    stored_file.storage_path = stored_upload.relative_path
    stored_file.content_type = stored_upload.content_type
    stored_file.size_bytes = stored_upload.size_bytes
    db.commit()
    db.refresh(stored_file)
    return stored_file


@router.put("/{file_id}/shares", response_model=ShareListResponse)
def replace_file_shares(
    file_id: int,
    payload: ShareListRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ShareListResponse:
    stored_file = _get_file_or_404(db, file_id)
    _require_owner(current_user, stored_file)
    stored_file.shares.clear()
    normalized_emails = sorted(
        {normalize_email(str(email)) for email in payload.recipient_emails}
    )
    for email in normalized_emails:
        stored_file.shares.append(FileShare(recipient_email=email))
    db.commit()
    return ShareListResponse(recipient_emails=normalized_emails)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[LocalFileStorage, Depends(get_storage)],
) -> Response:
    stored_file = _get_file_or_404(db, file_id)
    _require_owner(current_user, stored_file)
    storage_path = stored_file.storage_path
    db.delete(stored_file)
    db.commit()
    storage.delete(storage_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
