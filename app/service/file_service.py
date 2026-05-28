from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class FileService:
    """文件生命周期服务。

    流程：本地临时文件 -> 上传 S3 -> 本地清理。
    """

    def EnsureTempDir(self, temp_dir: str) -> Path:
        path = Path(temp_dir).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path

        resolved_path = path.resolve()
        resolved_path.mkdir(parents=True, exist_ok=True)
        return resolved_path
