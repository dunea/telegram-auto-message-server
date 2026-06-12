"""AsyncFileService.CleanupExpiredFiles 异步测试（PR #11 收尾后）。

说明：
- 覆盖 ``AsyncFileService`` 清理过期文件路径（PR #11 收尾前称 AsyncFileService，收尾后为 FileService）；
- async repository 用 ``AsyncMock`` 模拟；
- async s3 adapter 用 ``AsyncMock`` 模拟；
- 业务行为与原 ``test_file_cleanup.py`` 一致（PR #11 收尾前测 sync FileService）。
"""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.config import Settings
from app.service.file_service import FileService


def _build_settings(tmp_path: Path) -> Settings:
    return Settings(
        mode="api",
        jwt_secret_key="unit-test-secret",
        local_temp_dir=str(tmp_path),
    )


def test_cleanup_expired_files_marks_deleted_and_removes_local(tmp_path: Path) -> None:
    expired_pending_path = tmp_path / "expired_pending.txt"
    expired_pending_path.write_bytes(b"pending")

    expired_uploaded_path = tmp_path / "expired_uploaded.txt"
    expired_uploaded_path.write_bytes(b"uploaded")

    not_expired_path = tmp_path / "not_expired.txt"
    not_expired_path.write_bytes(b"alive")

    now = datetime.now(timezone.utc)
    records = [
        SimpleNamespace(
            id=1,
            local_path=str(expired_pending_path),
            s3_key=None,
            status="pending",
            expires_at=now - timedelta(hours=1),
        ),
        SimpleNamespace(
            id=2,
            local_path=str(expired_uploaded_path),
            s3_key="uploads/expired_uploaded.txt",
            status="uploaded",
            expires_at=now - timedelta(hours=2),
        ),
        SimpleNamespace(
            id=3,
            local_path=str(not_expired_path),
            s3_key=None,
            status="pending",
            expires_at=now + timedelta(hours=2),
        ),
    ]

    fake_repository = AsyncMock()
    fake_repository.FindAllByStatusAndExpiresAtBefore = AsyncMock(side_effect=[
        [records[0]],  # pending batch
        [records[1]],  # uploaded batch
    ])

    fake_s3_adapter = AsyncMock()
    fake_s3_adapter.DeleteFile = AsyncMock(return_value=True)

    fake_session = AsyncMock()
    fake_session.commit = AsyncMock(return_value=None)

    service = FileService(
        settings=_build_settings(tmp_path),
        session=fake_session,  # type: ignore[arg-type]
        file_record_repository=fake_repository,  # type: ignore[arg-type]
        s3_adapter=fake_s3_adapter,  # type: ignore[arg-type]
    )

    result = asyncio.run(service.CleanupExpiredFiles())

    assert result["cleaned"] == 2
    assert result["s3_delete_failed"] == 0
    fake_session.commit.assert_awaited_once()

    assert records[0].status == "deleted"
    assert records[1].status == "deleted"
    assert records[2].status == "pending"

    assert expired_pending_path.exists() is False
    assert expired_uploaded_path.exists() is False
    assert not_expired_path.exists() is True
    fake_s3_adapter.DeleteFile.assert_awaited_once_with(key="uploads/expired_uploaded.txt")
