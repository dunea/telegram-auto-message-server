from pathlib import Path
from datetime import datetime, timedelta, timezone
import uuid
import mimetypes
import logging

from sqlalchemy.orm import Session

from app.adapter.s3_adapter import S3Adapter
from app.config import Settings
from app.models.file import FileRecord
from app.repository.file_repository import SqlAlchemyFileRecordRepository


PROJECT_ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)


class FileService:
    """文件生命周期服务。

    流程：本地临时文件 -> 上传 S3 -> 本地清理。
    """

    def __init__(
        self,
        settings: Settings,
        session: Session,
        file_record_repository: SqlAlchemyFileRecordRepository,
        s3_adapter: S3Adapter,
    ) -> None:
        self._settings = settings
        self._session = session
        self._file_record_repository = file_record_repository
        self._s3_adapter = s3_adapter

    def EnsureTempDir(self, temp_dir: str) -> Path:
        path = Path(temp_dir).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path

        resolved_path = path.resolve()
        resolved_path.mkdir(parents=True, exist_ok=True)
        return resolved_path

    @staticmethod
    def _safe_filename(filename: str) -> str:
        sanitized = filename.replace("\\", "_").replace("/", "_").strip()
        return sanitized or "unnamed.bin"

    @staticmethod
    def _to_item(file_record: FileRecord) -> dict:
        filename = Path(file_record.local_path).name
        return {
            "file_id": int(file_record.id),
            "filename": filename,
            "status": file_record.status,
            "size_bytes": int(file_record.file_size_bytes),
            "s3_key": file_record.s3_key,
            "s3_url": file_record.s3_url,
            "created_at": file_record.created_at.isoformat() if file_record.created_at else None,
            "expires_at": file_record.expires_at.isoformat() if file_record.expires_at else None,
        }

    def UploadFile(self, filename: str, content: bytes) -> dict:
        """上传文件：先落本地，再尝试上传 S3。"""
        if not content:
            raise ValueError("文件内容不能为空")

        temp_dir = self.EnsureTempDir(self._settings.local_temp_dir)
        safe_name = self._safe_filename(filename)
        file_token = uuid.uuid4().hex
        local_path = temp_dir / f"{file_token}_{safe_name}"
        local_path.write_bytes(content)

        size_bytes = local_path.stat().st_size
        if size_bytes > int(self._settings.local_temp_max_bytes):
            local_path.unlink(missing_ok=True)
            raise ValueError("文件大小超出本地暂存上限")

        expires_at = datetime.utcnow() + timedelta(hours=int(self._settings.local_temp_retention_hours))
        file_record = FileRecord(
            local_path=str(local_path),
            s3_key=None,
            s3_url=None,
            file_size_bytes=int(size_bytes),
            status="pending",
            expires_at=expires_at,
        )
        self._file_record_repository.Save(file_record)
        self._session.flush()

        object_key = f"uploads/{datetime.utcnow().strftime('%Y%m%d')}/{file_token}_{safe_name}"
        s3_url = ""
        try:
            s3_url = self._s3_adapter.UploadFile(local_path=str(local_path), key=object_key)
        except Exception:
            logger.exception(
                "S3 上传失败，文件保留 pending 状态以便后续补偿",
                extra={"object_key": object_key, "local_path": str(local_path)},
            )

        if s3_url:
            file_record.s3_key = object_key
            file_record.s3_url = s3_url
            file_record.status = "uploaded"
        else:
            logger.warning(
                "文件未上传到 S3，当前保持 pending 状态",
                extra={"object_key": object_key, "file_record_id": int(file_record.id or 0)},
            )

        self._session.commit()
        result = self._to_item(file_record)
        return {
            "file_id": result["file_id"],
            "filename": result["filename"],
            "status": result["status"],
            "size_bytes": result["size_bytes"],
            "s3_key": result["s3_key"],
            "s3_url": result["s3_url"],
        }

    def ListFiles(self, status: str | None, limit: int, offset: int) -> dict:
        items = self._file_record_repository.FindAllOrderByIdDesc(limit=limit, offset=offset, status=status)
        total = self._file_record_repository.CountByStatus(status=status)
        return {
            "total": int(total),
            "items": [self._to_item(item) for item in items],
        }

    def GetFileById(self, file_id: int) -> dict:
        file_record = self._file_record_repository.FindById(file_id)
        if file_record is None:
            raise ValueError("文件不存在")
        return self._to_item(file_record)

    def DownloadFile(self, file_id: int) -> tuple[bytes, str, str]:
        """下载文件，返回 (内容, 文件名, MIME)。"""
        file_record = self._file_record_repository.FindById(file_id)
        if file_record is None:
            raise ValueError("文件不存在")
        if file_record.status == "deleted":
            raise ValueError("文件已删除")

        local_path = Path(file_record.local_path)
        if not local_path.exists() and file_record.s3_key:
            self._s3_adapter.DownloadFile(key=file_record.s3_key, local_path=str(local_path))

        if not local_path.exists():
            raise ValueError("文件不可用")

        content = local_path.read_bytes()
        filename = local_path.name
        mime_type, _ = mimetypes.guess_type(filename)
        return content, filename, mime_type or "application/octet-stream"

    def SoftDeleteFile(self, file_id: int) -> dict:
        file_record = self._file_record_repository.FindById(file_id)
        if file_record is None:
            raise ValueError("文件不存在")

        if file_record.s3_key:
            self._s3_adapter.DeleteFile(key=file_record.s3_key)

        Path(file_record.local_path).unlink(missing_ok=True)
        file_record.status = "deleted"
        self._session.commit()
        result = self._to_item(file_record)
        return {
            "file_id": result["file_id"],
            "filename": result["filename"],
            "status": result["status"],
            "size_bytes": result["size_bytes"],
            "s3_key": result["s3_key"],
            "s3_url": result["s3_url"],
        }

    def CleanupExpiredFiles(self, batch_limit: int = 200) -> dict[str, int]:
        """清理过期文件。

        说明：
        1. 仅处理 pending/uploaded 且 expires_at 已过期的记录；
        2. 清理本地文件与 S3 对象后，将状态统一置为 deleted。
        """
        now = datetime.now(timezone.utc)
        cleaned = 0
        s3_delete_failed = 0

        for status in ("pending", "uploaded"):
            expired_records = self._file_record_repository.FindAllByStatusAndExpiresAtBefore(
                status=status,
                expires_before=now,
                limit=batch_limit,
            )
            for file_record in expired_records:
                local_path = Path(file_record.local_path)
                local_path.unlink(missing_ok=True)

                if file_record.s3_key:
                    try:
                        self._s3_adapter.DeleteFile(key=file_record.s3_key)
                    except Exception:
                        s3_delete_failed += 1
                        logger.exception(
                            "清理过期文件时删除 S3 对象失败",
                            extra={"file_record_id": int(file_record.id), "s3_key": file_record.s3_key},
                        )

                file_record.status = "deleted"
                cleaned += 1

        self._session.commit()
        return {"cleaned": cleaned, "s3_delete_failed": s3_delete_failed}
