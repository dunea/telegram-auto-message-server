from pathlib import Path
from datetime import datetime, timedelta, timezone
import uuid
import mimetypes
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.s3_adapter import S3Adapter
from app.config import Settings
from app.models.file import FileRecord
from app.repository.file_repository import (
    SqlAlchemyFileRecordRepository,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)

class FileService:
    """文件生命周期服务（异步版本，PR #4 引入，PR #10 切 aioboto3）。

    说明：
    1. 与 ``FileService``（同步）并存到 PR #11 收尾；
    2. aioboto3 原生 async 调用（PR #10 切 aioboto3，桥接已删除）；
    3. 私有 3 个无 IO 辅助方法（EnsureTempDir / _safe_filename / _to_item）与 sync 版一致保持同步。
    """

    def __init__(
        self,
        settings: Settings,
        session: AsyncSession,
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

    async def UploadFile(self, filename: str, content: bytes, owner_user_id: int | None = None) -> dict:
        if not content:
            raise ValueError("文件内容不能为空")

        # 1. 校验文件大小限制 (最大 5MB)
        max_size_bytes = 5 * 1024 * 1024  # 5MB
        if len(content) > max_size_bytes:
            raise ValueError("文件大小超出限制，最大允许 5MB")

        # 2. 校验文件类型 (Telegram 支持的主流媒体和文档后缀)
        safe_name = self._safe_filename(filename)
        ext = Path(safe_name).suffix.lstrip(".").lower()
        allowed_extensions = {
            "jpg", "jpeg", "png", "gif", "webp",
            "mp4", "mov", "avi",
            "mp3", "ogg", "wav", "m4a",
            "pdf", "txt", "doc", "docx", "xls", "xlsx",
            "zip", "rar", "7z"
        }
        if ext not in allowed_extensions:
            raise ValueError(f"不支持的文件类型 '.{ext}'，仅支持图片、视频、音频、文档及压缩包格式")

        temp_dir = self.EnsureTempDir(self._settings.local_temp_dir)
        file_token = uuid.uuid4().hex
        local_path = temp_dir / f"{file_token}_{safe_name}"
        local_path.write_bytes(content)

        size_bytes = local_path.stat().st_size
        if size_bytes > int(self._settings.local_temp_max_bytes):
            local_path.unlink(missing_ok=True)
            raise ValueError("文件大小超出本地暂存上限")

        # 判断 S3 是否启用
        s3_enabled = self._s3_adapter._enabled()

        if s3_enabled:
            expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=int(self._settings.local_temp_retention_hours))
            file_record = FileRecord(
                local_path=str(local_path),
                s3_key=None,
                s3_url=None,
                file_size_bytes=int(size_bytes),
                status="pending",
                expires_at=expires_at,
                owner_user_id=owner_user_id,
            )
            await self._file_record_repository.Save(file_record)
            await self._session.flush()

            object_key = f"uploads/{datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y%m%d')}/{file_token}_{safe_name}"
            s3_url = ""
            try:
                s3_url = await self._s3_adapter.UploadFile(
                    local_path=str(local_path),
                    key=object_key,
                )
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
        else:
            # 本地持久化模式：将文件移动到本地持久化文件夹
            persistent_dir = self.EnsureTempDir(self._settings.local_storage_dir)
            persistent_path = persistent_dir / f"{file_token}_{safe_name}"
            try:
                import shutil
                shutil.move(str(local_path), str(persistent_path))
            except Exception:
                import shutil
                shutil.copy2(str(local_path), str(persistent_path))
                local_path.unlink(missing_ok=True)

            file_record = FileRecord(
                local_path=str(persistent_path),
                s3_key=None,
                s3_url=None,
                file_size_bytes=int(size_bytes),
                status="uploaded",  # 本地持久存储文件即为就绪
                expires_at=None,    # 设为 None 避免被定时清理
                owner_user_id=owner_user_id,
            )
            await self._file_record_repository.Save(file_record)

        await self._session.commit()
        result = self._to_item(file_record)
        return {
            "file_id": result["file_id"],
            "filename": result["filename"],
            "status": result["status"],
            "size_bytes": result["size_bytes"],
            "s3_key": result["s3_key"],
            "s3_url": result["s3_url"],
        }

    async def ListFiles(self, status: str | None, limit: int, offset: int, owner_user_id: int | None = None) -> dict:
        items = await self._file_record_repository.FindAllOrderByIdDesc(limit=limit, offset=offset, status=status, owner_user_id=owner_user_id)
        total = await self._file_record_repository.CountByStatus(status=status, owner_user_id=owner_user_id)
        return {
            "total": int(total),
            "items": [self._to_item(item) for item in items],
        }

    async def _get_file_or_raise(self, file_id: int, owner_user_id: int | None = None) -> FileRecord:
        file_record = await self._file_record_repository.FindById(file_id)
        if file_record is None:
            raise ValueError("文件不存在")
        if owner_user_id is not None and file_record.owner_user_id != owner_user_id:
            raise ValueError("文件不存在")
        return file_record

    async def GetFileById(self, file_id: int, owner_user_id: int | None = None) -> dict:
        file_record = await self._get_file_or_raise(file_id, owner_user_id)
        return self._to_item(file_record)

    async def DownloadFile(self, file_id: int, owner_user_id: int | None = None) -> tuple[bytes, str, str]:
        file_record = await self._get_file_or_raise(file_id, owner_user_id)
        if file_record.status == "deleted":
            raise ValueError("文件已删除")

        local_path = Path(file_record.local_path)
        if not local_path.exists() and file_record.s3_key:
            await self._s3_adapter.DownloadFile(
                key=file_record.s3_key,
                local_path=str(local_path),
            )

        if not local_path.exists():
            raise ValueError("文件不可用")

        content = local_path.read_bytes()
        filename = local_path.name
        mime_type, _ = mimetypes.guess_type(filename)
        return content, filename, mime_type or "application/octet-stream"

    async def SoftDeleteFile(self, file_id: int, owner_user_id: int | None = None) -> dict:
        file_record = await self._get_file_or_raise(file_id, owner_user_id)

        if file_record.s3_key:
            await self._s3_adapter.DeleteFile(key=file_record.s3_key)

        Path(file_record.local_path).unlink(missing_ok=True)
        file_record.status = "deleted"
        await self._session.commit()
        result = self._to_item(file_record)
        return {
            "file_id": result["file_id"],
            "filename": result["filename"],
            "status": result["status"],
            "size_bytes": result["size_bytes"],
            "s3_key": result["s3_key"],
            "s3_url": result["s3_url"],
        }

    async def CleanupExpiredFiles(self, batch_limit: int = 200) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        cleaned = 0
        s3_delete_failed = 0

        for status in ("pending", "uploaded"):
            expired_records = await self._file_record_repository.FindAllByStatusAndExpiresAtBefore(
                status=status,
                expires_before=now,
                limit=batch_limit,
            )
            for file_record in expired_records:
                local_path = Path(file_record.local_path)
                local_path.unlink(missing_ok=True)

                if file_record.s3_key:
                    try:
                        await self._s3_adapter.DeleteFile(key=file_record.s3_key)
                    except Exception:
                        s3_delete_failed += 1
                        logger.exception(
                            "清理过期文件时删除 S3 对象失败",
                            extra={"file_record_id": int(file_record.id), "s3_key": file_record.s3_key},
                        )

                file_record.status = "deleted"
                cleaned += 1

        await self._session.commit()
        return {"cleaned": cleaned, "s3_delete_failed": s3_delete_failed}
