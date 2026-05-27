from pathlib import Path


class FileService:
    """文件生命周期服务。

    流程：本地临时文件 -> 上传 S3 -> 本地清理。
    """

    def EnsureTempDir(self, temp_dir: str) -> Path:
        path = Path(temp_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
