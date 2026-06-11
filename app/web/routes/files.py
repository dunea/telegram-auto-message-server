import logging
from urllib.parse import quote
from fastapi import APIRouter, Depends, Request, UploadFile, File, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_file_service
from app.models.file import FileRecord
from app.service.file_service import FileService
from app.web import templates
from app.web.dependencies import get_current_user_from_cookie

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/web", tags=["web-files"])


@router.get("/files", response_class=HTMLResponse)
async def list_files(
    request: Request,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: Session = Depends(get_db_session),
):
    # SQLAlchemy 查询 FileRecord
    stmt = select(FileRecord).order_by(FileRecord.id.desc())
    files = db_session.scalars(stmt).all()

    return templates.TemplateResponse(
        "files/list.html",
        {
            "request": request,
            "user_id": user_id,
            "files": files,
        },
    )


@router.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    content = await file.read()
    file_service.UploadFile(filename=file.filename or "unnamed", content=content)
    return RedirectResponse(url="/web/files", status_code=303)


@router.post("/files/{file_id}/delete")
async def delete_file(
    file_id: int,
    file_service: FileService = Depends(get_file_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    try:
        file_service.SoftDeleteFile(file_id=file_id)
    except ValueError as e:
        logger.warning(f"删除文件失败: {e}")
    return RedirectResponse(url="/web/files", status_code=303)


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int,
    file_service: FileService = Depends(get_file_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    try:
        content, filename, mime_type = file_service.DownloadFile(file_id=file_id)
        encoded_filename = quote(filename)
        return Response(
            content=content,
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}"
            },
        )
    except ValueError as e:
        logger.error(f"下载文件失败: {e}")
        return HTMLResponse(content=f"<h3>下载文件出错: {str(e)}</h3>", status_code=404)
