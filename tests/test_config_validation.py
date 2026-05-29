"""配置校验测试。"""

import pytest

from app.config import Settings


def test_mode_is_normalized_to_lowercase() -> None:
    settings = Settings(mode="API", jwt_secret_key="unit-test-secret")
    assert settings.mode == "api"


def test_pool_mode_requires_telegram_credentials() -> None:
    with pytest.raises(ValueError, match="telegram_api_id"):
        Settings(
            mode="pool",
            telegram_api_id=0,
            telegram_api_hash="",
            jwt_secret_key="unit-test-secret",
        )


def test_pool_mode_accepts_valid_telegram_credentials() -> None:
    settings = Settings(
        mode="pool",
        telegram_api_id=123456,
        telegram_api_hash="hash-value",
        jwt_secret_key="unit-test-secret",
    )
    assert settings.mode == "pool"
    assert settings.telegram_api_id == 123456
