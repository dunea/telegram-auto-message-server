"""文件管理 API 路由。"""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.api.deps import get_current_user, get_file_service
from app.schema.file import FileItemResponse, FileListResponse, UploadFileResponse
from app.service.file_service import FileService

router = APIRouter(prefix="/files", tags=["files"], dependencies=[Depends(get_current_user)])


@router.post("/upload", response_model=UploadFileResponse)
async def upload_file(
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service),
) -> UploadFileResponse:
    """上传文件。"""
    try:
        content = await file.read()
        result = file_service.UploadFile(filename=file.filename or "unnamed.bin", content=content)
        return UploadFileResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=FileListResponse)
async def list_files(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    file_service: FileService = Depends(get_file_service),
) -> FileListResponse:
    """查询文件列表。"""
    result = file_service.ListFiles(status=status, limit=limit, offset=offset)
    return FileListResponse(**result)


@router.get("/{file_id}", response_model=FileItemResponse)
async def get_file_item(
    file_id: int,
    file_service: FileService = Depends(get_file_service),
) -> FileItemResponse:
    """查询单个文件信息。"""
    try:
        result = file_service.GetFileById(file_id=file_id)
        return FileItemResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{file_id}/download")
async def download_file(
    file_id: int,
    file_service: FileService = Depends(get_file_service),
) -> Response:
    """下载文件。"""
    try:
        content, filename, mime_type = file_service.DownloadFile(file_id=file_id)
        return Response(
            content=content,
            media_type=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    file_service: FileService = Depends(get_file_service),
) -> dict:
    """软删除文件。"""
    try:
        return file_service.SoftDeleteFile(file_id=file_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
