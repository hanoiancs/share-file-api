from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from internal_static_files.models import ShareMode


class FileOwnerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str | None


class FileShareResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_id: int
    recipient_email: str


class FileMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    title: str
    description: str | None
    original_filename: str
    content_type: str
    share_mode: ShareMode
    size_bytes: int
    created_at: datetime
    updated_at: datetime
    owner: FileOwnerResponse
    shares: list[FileShareResponse]


class PaginatedFilesResponse(BaseModel):
    items: list[FileMetadataResponse]
    page: int
    per_page: int
    total: int
    total_pages: int


class FileUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    share_mode: ShareMode | None = None


class ShareListRequest(BaseModel):
    recipient_emails: list[EmailStr]


class ShareListResponse(BaseModel):
    recipient_emails: list[str]
