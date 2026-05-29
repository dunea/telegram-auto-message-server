"""文件过期清理测试。"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from app.config import Settings
from app.service.file_service import FileService


class FakeFileRepository:
    def __init__(self, records: list[SimpleNamespace]) -> None:
        self._records = records

    def FindAllByStatusAndExpiresAtBefore(self, status: str, expires_before: datetime, limit: int) -> list[SimpleNamespace]:
        matched = [
            item
            for item in self._records
            if item.status == status and item.expires_at is not None and item.expires_at <= expires_before
        ]
        return matched[: max(1, int(limit))]


class FakeS3Adapter:
    def __init__(self) -> None:
        self.deleted_keys: list[str] = []

    def DeleteFile(self, key: str) -> bool:
        self.deleted_keys.append(key)
        return True


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

    fake_repository = FakeFileRepository(records)
    fake_s3_adapter = FakeS3Adapter()

    committed = {"value": False}

    class FakeSession:
        def commit(self) -> None:
            committed["value"] = True

    service = FileService(
        settings=_build_settings(tmp_path),
        session=FakeSession(),
        file_record_repository=fake_repository,  # type: ignore[arg-type]
        s3_adapter=fake_s3_adapter,  # type: ignore[arg-type]
    )

    result = service.CleanupExpiredFiles()

    assert result["cleaned"] == 2
    assert result["s3_delete_failed"] == 0
    assert committed["value"] is True

    assert records[0].status == "deleted"
    assert records[1].status == "deleted"
    assert records[2].status == "pending"

    assert expired_pending_path.exists() is False
    assert expired_uploaded_path.exists() is False
    assert not_expired_path.exists() is True
    assert fake_s3_adapter.deleted_keys == ["uploads/expired_uploaded.txt"]
