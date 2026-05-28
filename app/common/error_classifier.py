import asyncio

from app.models.enums import ErrorClass


def classify_exception(exc: Exception) -> tuple[ErrorClass, bool, bool]:
    """按异常对象分类登录/调用错误。

    返回：
    1. error_class: timeout/auth/network/unknown
    2. retryable: 是否可重试
    3. is_timeout: 是否属于超时错误（用于专门计数）
    """
    error_text = str(exc).lower()
    timeout_keywords = ("timeout", "timed out")
    auth_keywords = (
        "auth",
        "unauthorized",
        "forbidden",
        "password",
        "api_id",
        "api_hash",
        "session",
        "phone_code_invalid",
    )
    network_keywords = ("network", "connection", "reset", "dns")

    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or any(k in error_text for k in timeout_keywords):
        return ErrorClass.TIMEOUT, True, True
    if any(k in error_text for k in auth_keywords):
        return ErrorClass.AUTH, False, False
    if any(k in error_text for k in network_keywords):
        return ErrorClass.NETWORK, True, False
    return ErrorClass.UNKNOWN, True, False


def classify_error_message(error_message: str | None) -> ErrorClass:
    """按错误文本分类，主要用于日志聚合与执行记录标注。"""
    if not error_message:
        return ErrorClass.NONE

    normalized = error_message.lower()
    if "timeout" in normalized or "timed out" in normalized:
        return ErrorClass.TIMEOUT
    if (
        "auth" in normalized
        or "unauthorized" in normalized
        or "forbidden" in normalized
        or "password" in normalized
        or "api_id" in normalized
        or "api_hash" in normalized
        or "session" in normalized
        or "phone_code_invalid" in normalized
    ):
        return ErrorClass.AUTH
    if (
        "network" in normalized
        or "connection" in normalized
        or "reset" in normalized
        or "dns" in normalized
    ):
        return ErrorClass.NETWORK
    return ErrorClass.UNKNOWN
