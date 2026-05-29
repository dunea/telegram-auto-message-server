from pathlib import Path

import boto3

from app.config import Settings


class S3Adapter:
    """S3 适配器。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None

    def _enabled(self) -> bool:
        return bool(self._settings.s3_bucket_name and self._settings.s3_access_key_id and self._settings.s3_secret_access_key)

    def _get_client(self):
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=(self._settings.s3_endpoint_url or None),
                aws_access_key_id=self._settings.s3_access_key_id,
                aws_secret_access_key=self._settings.s3_secret_access_key,
                region_name=(self._settings.s3_region_name or None),
            )
        return self._client

    def UploadFile(self, local_path: str, key: str) -> str:
        """上传文件并返回对象 URL。"""
        if not self._enabled():
            return ""
        path = Path(local_path)
        if not path.exists() or not path.is_file():
            raise ValueError("上传文件不存在")
        client = self._get_client()
        with path.open("rb") as fp:
            client.upload_fileobj(fp, self._settings.s3_bucket_name, key)

        if self._settings.s3_endpoint_url:
            endpoint = self._settings.s3_endpoint_url.rstrip("/")
            return f"{endpoint}/{self._settings.s3_bucket_name}/{key}"
        region = self._settings.s3_region_name or "us-east-1"
        return f"https://{self._settings.s3_bucket_name}.s3.{region}.amazonaws.com/{key}"

    def DownloadFile(self, key: str, local_path: str) -> bool:
        """下载对象到本地。"""
        if not self._enabled():
            return False
        target = Path(local_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        client = self._get_client()
        with target.open("wb") as fp:
            client.download_fileobj(self._settings.s3_bucket_name, key, fp)
        return True

    def DeleteFile(self, key: str) -> bool:
        """删除 S3 对象。"""
        if not self._enabled():
            return False
        client = self._get_client()
        client.delete_object(Bucket=self._settings.s3_bucket_name, Key=key)
        return True
