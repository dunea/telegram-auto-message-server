"""S3Adapter 单元测试。

PR #10 引入 S3Adapter 后，需要覆盖：
1. 三个方法在 S3 未配置（disabled）路径下的行为；
2. 三个方法在 S3 已配置（enabled）路径下是否正确构造 aioboto3 client context。

说明：
- disabled 路径不访问网络，直接断言返回默认值；
- enabled 路径通过 ``S3Adapter(settings, session=fake)`` 注入 fake session，
  避免真实网络与对 aioboto3 内部协程链的依赖。
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from app.adapter.s3_adapter import S3Adapter
from app.config import Settings


def _build_settings(**overrides) -> Settings:
    defaults = dict(
        mode="api",
        jwt_secret_key="unit-test-secret",
        s3_bucket_name="",
        s3_access_key_id="",
        s3_secret_access_key="",
        s3_endpoint_url="",
        s3_region_name="",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _build_fake_session(fake_client: MagicMock) -> MagicMock:
    """构造一个 fake session，client() 返回支持 ``async with`` 的 ctx manager。"""
    fake_client_ctx = MagicMock()
    fake_client_ctx.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client_ctx.__aexit__ = AsyncMock(return_value=None)

    fake_session = MagicMock()
    fake_session.client = MagicMock(return_value=fake_client_ctx)
    return fake_session


# ==========================
# disabled 路径（不访问网络）
# ==========================


def test_async_upload_disabled_returns_empty_string() -> None:
    """未配置 S3 时，UploadFile 直接返回空字符串。"""
    settings = _build_settings()
    adapter = S3Adapter(settings=settings)
    result = asyncio.run(adapter.UploadFile(local_path="ignored", key="uploads/x.txt"))
    assert result == ""


def test_async_download_disabled_returns_false() -> None:
    """未配置 S3 时，DownloadFile 直接返回 False。"""
    settings = _build_settings()
    adapter = S3Adapter(settings=settings)
    result = asyncio.run(adapter.DownloadFile(key="uploads/x.txt", local_path="/tmp/x.txt"))
    assert result is False


def test_async_delete_disabled_returns_false() -> None:
    """未配置 S3 时，DeleteFile 直接返回 False。"""
    settings = _build_settings()
    adapter = S3Adapter(settings=settings)
    result = asyncio.run(adapter.DeleteFile(key="uploads/x.txt"))
    assert result is False


# ==========================
# enabled 路径（注入 fake session）
# ==========================


def _build_enabled_settings(tmp_path: Path) -> Settings:
    return _build_settings(
        s3_bucket_name="test-bucket",
        s3_access_key_id="AKIAFAKE",
        s3_secret_access_key="secretfake",
        s3_endpoint_url="",
        s3_region_name="us-east-1",
        local_temp_dir=str(tmp_path),
    )


def test_async_upload_enabled_invokes_client_upload_fileobj(tmp_path: Path) -> None:
    """启用 S3 时，UploadFile 应在 aioboto3 client 上下文内调 upload_fileobj。"""
    settings = _build_enabled_settings(tmp_path)
    local_file = tmp_path / "payload.bin"
    local_file.write_bytes(b"hello-world")

    fake_client = MagicMock()
    fake_client.upload_fileobj = AsyncMock(return_value=None)
    fake_session = _build_fake_session(fake_client)

    adapter = S3Adapter(settings=settings, session=fake_session)
    result = asyncio.run(adapter.UploadFile(local_path=str(local_file), key="uploads/20250101/payload.bin"))

    assert result == "https://test-bucket.s3.us-east-1.amazonaws.com/uploads/20250101/payload.bin"
    fake_session.client.assert_called_once()
    kwargs = fake_session.client.call_args.kwargs
    assert kwargs["endpoint_url"] is None  # Settings s3_endpoint_url="" 走 (x or None) 分支
    assert kwargs["aws_access_key_id"] == "AKIAFAKE"
    assert kwargs["aws_secret_access_key"] == "secretfake"
    assert kwargs["region_name"] == "us-east-1"
    fake_client.upload_fileobj.assert_awaited_once()


def test_async_download_enabled_invokes_client_download_fileobj(tmp_path: Path) -> None:
    """启用 S3 时，DownloadFile 应在 aioboto3 client 上下文内调 download_fileobj。"""
    settings = _build_enabled_settings(tmp_path)
    target = tmp_path / "downloaded.bin"

    fake_client = MagicMock()
    fake_client.download_fileobj = AsyncMock(return_value=None)
    fake_session = _build_fake_session(fake_client)

    adapter = S3Adapter(settings=settings, session=fake_session)
    result = asyncio.run(adapter.DownloadFile(key="uploads/x.bin", local_path=str(target)))

    assert result is True
    fake_client.download_fileobj.assert_awaited_once()
    args, _ = fake_client.download_fileobj.call_args
    assert args[0] == "test-bucket"
    assert args[1] == "uploads/x.bin"


def test_async_delete_enabled_invokes_client_delete_object(tmp_path: Path) -> None:
    """启用 S3 时，DeleteFile 应在 aioboto3 client 上下文内调 delete_object。"""
    settings = _build_enabled_settings(tmp_path)

    fake_client = MagicMock()
    fake_client.delete_object = AsyncMock(return_value=None)
    fake_session = _build_fake_session(fake_client)

    adapter = S3Adapter(settings=settings, session=fake_session)
    result = asyncio.run(adapter.DeleteFile(key="uploads/x.bin"))

    assert result is True
    fake_client.delete_object.assert_awaited_once_with(Bucket="test-bucket", Key="uploads/x.bin")


def test_async_upload_uses_endpoint_url_in_return_value(tmp_path: Path) -> None:
    """配置了 endpoint_url 时，UploadFile 返回值应拼接 endpoint_url。"""
    settings = _build_settings(
        s3_bucket_name="bucket",
        s3_access_key_id="ak",
        s3_secret_access_key="sk",
        s3_endpoint_url="https://minio.local:9000/",
        s3_region_name="us-east-1",
        local_temp_dir=str(tmp_path),
    )
    local_file = tmp_path / "x.txt"
    local_file.write_bytes(b"x")

    fake_client = MagicMock()
    fake_client.upload_fileobj = AsyncMock(return_value=None)
    fake_session = _build_fake_session(fake_client)

    adapter = S3Adapter(settings=settings, session=fake_session)
    result = asyncio.run(adapter.UploadFile(local_path=str(local_file), key="uploads/x.txt"))

    assert result == "https://minio.local:9000/bucket/uploads/x.txt"
