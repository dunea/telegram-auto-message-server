from pydantic import BaseModel, Field


class UploadFileResponse(BaseModel):
    """文件上传响应。"""

    file_id: int
    filename: str
    status: str
    size_bytes: int
    s3_key: str | None = None
    s3_url: str | None = None


class FileItemResponse(BaseModel):
    """文件条目响应。"""

    file_id: int
    filename: str
    status: str
    size_bytes: int
    s3_key: str | None = None
    s3_url: str | None = None
    created_at: str | None = None
    expires_at: str | None = None


class FileListResponse(BaseModel):
    """文件列表响应。"""

    total: int
    items: list[FileItemResponse]


class ListFilesQuery(BaseModel):
    """文件列表查询参数模型。"""

    status: str | None = Field(default=None, max_length=32)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
