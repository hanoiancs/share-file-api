from math import ceil
from typing import Annotated
from urllib.parse import urlencode

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from sqlalchemy import delete, func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from internal_static_files.auth import (
    decode_access_token,
    get_current_user,
    oauth2_scheme,
)
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
    PaginatedFilesResponse,
    ShareListRequest,
    ShareListResponse,
)
from internal_static_files.sharing import can_read_file
from internal_static_files.storage import (
    LocalFileStorage,
    UnsupportedFileTypeError,
    UploadTooLargeError,
)


def require_allowed_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    access_token: Annotated[str | None, Cookie()] = None,
):
    if request.scope["route"].name != "get_file_content":
        user: User = get_current_user(db, settings, bearer_token, access_token)

        if len(settings.allowed_users) > 0:
            email = user.email
            if email not in settings.allowed_users:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="not allowed user",
                )


router = APIRouter(
    prefix="/files", tags=["files"], dependencies=[Depends(require_allowed_user)]
)

templates = Jinja2Templates(directory="templates")
templates.env.autoescape = False
templates.env.filters["markdown"] = render_markdown


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
        stored_upload = storage.write_upload(
            current_user.id, upload.filename or "upload", content
        )
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


@router.get("", response_model=PaginatedFilesResponse)
def list_files(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1)] = 25,
) -> PaginatedFilesResponse:
    offset = (page - 1) * per_page

    visibility_filter = StoredFile.owner_id == current_user.id

    total = db.exec(
        select(func.count(func.distinct(StoredFile.id)))
        .join(User, StoredFile.owner_id == User.id)
        .outerjoin(FileShare, FileShare.file_id == StoredFile.id)
        .where(visibility_filter)
    ).one()

    candidates = db.exec(
        select(StoredFile)
        .join(User, StoredFile.owner_id == User.id)
        .outerjoin(FileShare, FileShare.file_id == StoredFile.id)
        .where(visibility_filter)
        .options(selectinload(StoredFile.owner), selectinload(StoredFile.shares))
        .distinct()
        .order_by(StoredFile.id)
        .offset(offset)
        .limit(per_page)
    ).all()

    return PaginatedFilesResponse(
        items=list(candidates),
        page=page,
        per_page=per_page,
        total=total,
        total_pages=ceil(total / per_page) if total else 0,
    )


@router.get("/{file_id}", response_model=FileMetadataResponse)
def get_file(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StoredFile:
    stored_file = _get_file_or_404(db, file_id)
    _require_read(current_user, stored_file)
    return stored_file


@router.get("/{file_id}/content", name="get_file_content")
def get_file_content(
    file_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[LocalFileStorage, Depends(get_storage)],
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    access_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    token = bearer_token or access_token
    if token is None:
        return RedirectResponse(
            request.url_for("auth_google_login").include_query_params(
                handle_url=request.url_for("get_file_content", file_id=file_id)
            )
        )
    user_id = decode_access_token(token, settings)
    current_user = db.get(User, user_id)
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found"
        )
    stored_file = _get_file_or_404(db, file_id)
    _require_read(current_user, stored_file)
    content = storage.read(stored_file.storage_path)

    if stored_file.content_type == "markdown":
        # return HTMLResponse(render_markdown(content.decode("utf-8")))
        return templates.TemplateResponse(
            request=request,
            name="markdown.html",
            context={"content": content.decode("utf-8")},
            # context={"content": render_markdown(content.decode("utf-8"))},
        )

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
            previous_path,
            current_user.id,
            upload.filename or stored_file.original_filename,
            content,
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
    db.exec(delete(FileShare).where(FileShare.file_id == file_id))
    db.flush()
    for email in normalized_emails:
        db.add(FileShare(file_id=file_id, recipient_email=email))
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
