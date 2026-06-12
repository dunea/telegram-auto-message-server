from pathlib import Path

import aioboto3

from app.config import Settings


class S3Adapter:
    """S3 适配器（aioboto3 驱动，全链路 async 版本，PR #10 引入，PR #11 收尾）。

    说明：
    1. PR #10 阶段与 sync ``S3Adapter``（boto3 驱动）并存；
    2. PR #11 收尾删 sync 版，本类统一为全链路 async 唯一实现；
    3. 方法签名与 sync 版保持一致，便于 ``AsyncFileService`` 调用点零变化；
    4. aioboto3 client 必须在 ``async with`` 上下文中使用（``__aenter__`` / ``__aexit__``），
       每次调用都新建上下文，不缓存 client。
    """

    def __init__(self, settings: Settings, session=None) -> None:
        self._settings = settings
        self._session = session if session is not None else aioboto3.Session()

    def _enabled(self) -> bool:
        return bool(
            self._settings.s3_bucket_name
            and self._settings.s3_access_key_id
            and self._settings.s3_secret_access_key
        )

    def _client_kwargs(self) -> dict:
        return {
            "endpoint_url": self._settings.s3_endpoint_url or None,
            "aws_access_key_id": self._settings.s3_access_key_id,
            "aws_secret_access_key": self._settings.s3_secret_access_key,
            "region_name": self._settings.s3_region_name or None,
        }

    @staticmethod
    def _build_url(key: str, settings: Settings) -> str:
        if settings.s3_endpoint_url:
            endpoint = settings.s3_endpoint_url.rstrip("/")
            return f"{endpoint}/{settings.s3_bucket_name}/{key}"
        region = settings.s3_region_name or "us-east-1"
        return f"https://{settings.s3_bucket_name}.s3.{region}.amazonaws.com/{key}"

    async def UploadFile(self, local_path: str, key: str) -> str:
        """上传文件并返回对象 URL。"""
        if not self._enabled():
            return ""
        path = Path(local_path)
        if not path.exists() or not path.is_file():
            raise ValueError("上传文件不存在")
        async with self._session.client("s3", **self._client_kwargs()) as client:
            with path.open("rb") as fp:
                await client.upload_fileobj(fp, self._settings.s3_bucket_name, key)
        return self._build_url(key, self._settings)

    async def DownloadFile(self, key: str, local_path: str) -> bool:
        """下载对象到本地。"""
        if not self._enabled():
            return False
        target = Path(local_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        async with self._session.client("s3", **self._client_kwargs()) as client:
            with target.open("wb") as fp:
                await client.download_fileobj(self._settings.s3_bucket_name, key, fp)
        return True

    async def DeleteFile(self, key: str) -> bool:
        """删除 S3 对象。"""
        if not self._enabled():
            return False
        async with self._session.client("s3", **self._client_kwargs()) as client:
            await client.delete_object(Bucket=self._settings.s3_bucket_name, Key=key)
        return True
