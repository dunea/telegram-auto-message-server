from functools import lru_cache
import os
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
    api_scheduler_enabled: bool = Field(default=True, description="API 模式下是否启用业务消息任务调度器。如果部署了独立的 pool 实例，建议在 API 端设为 False。")

    pool_instance_id: str = "pool-1"
    pool_max_concurrent_logins: int = Field(default=20, ge=1)
    pool_total_shards: int = Field(default=1, ge=1)
    pool_shard_index: int = Field(default=0, ge=0)
    pool_login_scan_interval_seconds: int = Field(default=30, ge=5)
    pool_heartbeat_interval_seconds: int = Field(default=30, ge=5, description="号池实例心跳刷新与分片重新计算的间隔（秒）")
    pool_heartbeat_timeout_seconds: int = Field(default=120, ge=10, description="死节点心跳超时时间（秒），超过该时间的实例会被从分片计算中剔除")
    pool_message_cooldown_seconds: float = Field(default=5.0, ge=0.0, description="同一个账号发送消息的最小冷却时间（秒）")
    pool_login_timeout_seconds: int = Field(default=30, ge=5)
    pool_login_max_retries: int = Field(default=3, ge=1, le=10)
    pool_login_retry_backoff_seconds: int = Field(default=2, ge=1)
    pool_login_retry_jitter_ms: int = Field(default=200, ge=0)
    pool_client_idle_ttl_seconds: int = Field(default=300, ge=30)
    pool_client_max_failed_count: int = Field(default=3, ge=1)
    pool_client_cache_stats_interval: int = Field(default=100, ge=1)
    pool_round_degraded_success_rate_threshold: float = Field(default=0.7, ge=0, le=1)
    pool_round_degraded_timeout_fail_threshold: int = Field(default=3, ge=0)
    pool_shard_guard_enabled: bool = True

    mysql_dsn: str = "mysql+pymysql://root:root@127.0.0.1:3306/telegram_auto_message"

    telegram_api_id: int = 0
    telegram_api_hash: str = ""

    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_name: str = ""
    s3_region_name: str = ""

    jwt_secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=60, ge=1)
    jwt_refresh_token_expire_days: int = Field(default=30, ge=1)

    local_temp_dir: str = str(DEFAULT_LOCAL_TEMP_DIR)
    local_temp_max_bytes: int = 5 * 1024 * 1024 * 1024
    local_temp_retention_hours: int = Field(default=24 * 7, ge=1)
    local_cleanup_interval_minutes: int = Field(default=60, ge=1)

    db_pool_size: int = Field(default=25, ge=1, le=200)
    db_pool_max_overflow: int = Field(default=15, ge=0, le=200)
    db_pool_recycle_seconds: int = Field(default=3600, ge=30)
    db_pool_timeout_seconds: int = Field(default=30, ge=1)

    @model_validator(mode="after")
    def _validate_pool_shard(self) -> "Settings":
        mode = self.mode.strip().lower()
        if mode not in {"api", "pool"}:
            raise ValueError("mode 仅支持 api 或 pool")
        self.mode = mode

        if self.pool_shard_index >= self.pool_total_shards:
            raise ValueError("pool_shard_index 必须小于 pool_total_shards")

        # pool 模式必须配置 Telegram API 参数，避免运行到任务阶段才失败。
        if self.mode == "pool":
            if int(self.telegram_api_id) <= 0:
                raise ValueError("pool 模式下 telegram_api_id 必须大于 0")
            if not str(self.telegram_api_hash).strip():
                raise ValueError("pool 模式下 telegram_api_hash 不能为空")

        # 仅在非测试场景做最小安全提示，避免将示例密钥带到线上环境。
        if not os.getenv("PYTEST_CURRENT_TEST") and self.jwt_secret_key == "change-this-in-production":
            raise ValueError("jwt_secret_key 仍为示例值，请在 .env 中配置生产密钥")

        # 临时目录始终按“项目根目录”解析，避免启动 cwd 变化导致路径漂移。
        temp_dir = Path(self.local_temp_dir).expanduser()
        if not temp_dir.is_absolute():
            temp_dir = PROJECT_ROOT / temp_dir
        self.local_temp_dir = str(temp_dir.resolve())
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
