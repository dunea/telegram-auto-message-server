"""S3 禁用时的本地持久化存储测试。"""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from app.config import Settings
from app.models.file import FileRecord
from app.service.file_service import FileService


def _build_settings(tmp_path: Path) -> Settings:
    return Settings(
        mode="api",
        jwt_secret_key="unit-test-secret",
        local_temp_dir=str(tmp_path / "temp"),
        local_storage_dir=str(tmp_path / "persistent"),
    )


def test_local_storage_fallback_upload_and_delete(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    
    # 模拟数据层
    saved_records = []
    fake_repository = AsyncMock()
    
    async def fake_save(record: FileRecord):
        saved_records.append(record)
        record.id = 1
        return record
        
    fake_repository.Save = AsyncMock(side_effect=fake_save)
    
    # 模拟 S3 adapter 禁用
    fake_s3_adapter = MagicMock()
    fake_s3_adapter._enabled = MagicMock(return_value=False)
    
    fake_session = AsyncMock()
    
    service = FileService(
        settings=settings,
        session=fake_session,
        file_record_repository=fake_repository,
        s3_adapter=fake_s3_adapter,
    )
    
    # 执行文件上传
    filename = "test_image.png"
    file_content = b"fake-png-data"
    
    result = asyncio.run(service.UploadFile(
        filename=filename,
        content=file_content,
        owner_user_id=123,
    ))
    
    # 验证上传结果
    assert result["status"] == "uploaded"
    assert result["s3_key"] is None
    assert result["s3_url"] is None
    
    # 校验数据库保存的记录
    assert len(saved_records) == 1
    record = saved_records[0]
    assert record.status == "uploaded"
    assert record.expires_at is None
    assert record.owner_user_id == 123
    
    # 校验物理文件存放路径
    saved_path = Path(record.local_path)
    assert saved_path.exists()
    assert saved_path.read_bytes() == file_content
    # 应存放在持久化存储目录中
    assert "persistent" in record.local_path
    
    # 临时目录中的对应文件应当不再存在
    temp_dir = Path(settings.local_temp_dir)
    temp_files = list(temp_dir.glob("*"))
    assert len(temp_files) == 0
    
    # 模拟软删除该文件
    fake_repository.FindById = AsyncMock(return_value=record)
    
    delete_result = asyncio.run(service.SoftDeleteFile(
        file_id=1,
        owner_user_id=123,
    ))
    
    assert delete_result["status"] == "deleted"
    assert record.status == "deleted"
    # 验证物理文件被删除
    assert not saved_path.exists()


def test_file_upload_size_limit(tmp_path: Path) -> None:
    """测试上传超过 5MB 的文件时被拦截并抛出 ValueError。"""
    settings = _build_settings(tmp_path)
    fake_repository = AsyncMock()
    fake_s3_adapter = MagicMock()
    fake_session = AsyncMock()
    
    service = FileService(
        settings=settings,
        session=fake_session,
        file_record_repository=fake_repository,
        s3_adapter=fake_s3_adapter,
    )
    
    # 构造 5MB + 1 字节的数据
    large_content = b"a" * (5 * 1024 * 1024 + 1)
    
    import pytest
    with pytest.raises(ValueError) as exc_info:
        asyncio.run(service.UploadFile(
            filename="large_file.png",
            content=large_content,
            owner_user_id=123,
        ))
    assert "文件大小超出限制，最大允许 5MB" in str(exc_info.value)


def test_file_upload_type_limit(tmp_path: Path) -> None:
    """测试上传不支持的文件类型后缀时被拦截并抛出 ValueError。"""
    settings = _build_settings(tmp_path)
    fake_repository = AsyncMock()
    fake_s3_adapter = MagicMock()
    fake_session = AsyncMock()
    
    service = FileService(
        settings=settings,
        session=fake_session,
        file_record_repository=fake_repository,
        s3_adapter=fake_s3_adapter,
    )
    
    # 构造不支持的后缀，如 .exe 和 .msi
    import pytest
    for bad_ext in ["exe", "msi", "sh", "bat", "dll"]:
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(service.UploadFile(
                filename=f"malicious.{bad_ext}",
                content=b"some-content",
                owner_user_id=123,
            ))
        assert "不支持的文件类型" in str(exc_info.value)

