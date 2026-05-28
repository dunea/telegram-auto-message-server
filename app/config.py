from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCAL_TEMP_DIR = PROJECT_ROOT / "storage" / "temp_files"


class Settings(BaseSettings):
    """全局配置。

    说明：
    1. MODE 仅允许 api 或 pool。
    2. 文件先落本地临时目录，再异步上传到 S3。
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = "telegram-auto-message-server"
    mode: str = Field(default="api", description="运行模式：api 或 pool")
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    pool_instance_id: str = "pool-1"
    pool_max_concurrent_logins: int = Field(default=20, ge=1)
    pool_total_shards: int = Field(default=1, ge=1)
    pool_shard_index: int = Field(default=0, ge=0)
    pool_login_scan_interval_seconds: int = Field(default=30, ge=5)

    mysql_dsn: str = "mysql+pymysql://root:root@127.0.0.1:3306/telegram_auto_message"

    telegram_api_id: int = 0
    telegram_api_hash: str = ""

    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_name: str = ""
    s3_region_name: str = ""

    local_temp_dir: str = str(DEFAULT_LOCAL_TEMP_DIR)
    local_temp_max_bytes: int = 5 * 1024 * 1024 * 1024
    local_temp_retention_hours: int = 24 * 7
    local_cleanup_interval_minutes: int = 60

    @model_validator(mode="after")
    def _validate_pool_shard(self) -> "Settings":
        if self.pool_shard_index >= self.pool_total_shards:
            raise ValueError("pool_shard_index 必须小于 pool_total_shards")

        # 临时目录始终按“项目根目录”解析，避免启动 cwd 变化导致路径漂移。
        temp_dir = Path(self.local_temp_dir).expanduser()
        if not temp_dir.is_absolute():
            temp_dir = PROJECT_ROOT / temp_dir
        self.local_temp_dir = str(temp_dir.resolve())
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
