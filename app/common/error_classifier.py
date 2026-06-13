import asyncio

from app.models.enums import ErrorClass


def classify_exception(exc: Exception) -> tuple[ErrorClass, bool, bool]:
    """按异常对象分类登录/调用错误。

    返回：
    1. error_class: timeout/auth/network/flood/unknown
    2. retryable: 是否可重试
    3. is_timeout: 是否属于超时错误（用于专门计数）
    """
    class_name = exc.__class__.__name__

    # 优先基于具体的异常类进行类型判断，避免普通错误文本内容包含关键字时的误判
    if "TimeoutError" in class_name or isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return ErrorClass.TIMEOUT, True, True

    if "Flood" in class_name or hasattr(exc, "seconds"):
        return ErrorClass.FLOOD, True, False

    # 我们看看 Telethon 中的常见认证异常，它们在类名中包含特定的部分
    # 如 InvalidSessionError, SessionPasswordNeededError, AuthKeyUnregisteredError, PhoneNumberInvalidError
    if any(auth_err in class_name for auth_err in ("Auth", "Session", "Password", "PhoneNumber", "PhoneCode")):
        return ErrorClass.AUTH, False, False

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
        "deactivated",
        "unregistered",
        "expired",
        "revoked",
        "blocked",
        "peer_id",
        "peer id",
        "input peer",
    )
    network_keywords = ("network", "connection", "reset", "dns")
    flood_keywords = ("flood", "wait", "spam")

    if any(k in error_text for k in timeout_keywords):
        return ErrorClass.TIMEOUT, True, True
    if any(k in error_text for k in auth_keywords):
        return ErrorClass.AUTH, False, False
    if any(k in error_text for k in network_keywords):
        return ErrorClass.NETWORK, True, False
    if any(k in error_text for k in flood_keywords):
        return ErrorClass.FLOOD, True, False
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
        or "deactivated" in normalized
        or "unregistered" in normalized
        or "expired" in normalized
        or "revoked" in normalized
        or "blocked" in normalized
        or "peer_id" in normalized
        or "peer id" in normalized
        or "input peer" in normalized
    ):
        return ErrorClass.AUTH
    if (
        "network" in normalized
        or "connection" in normalized
        or "reset" in normalized
        or "dns" in normalized
    ):
        return ErrorClass.NETWORK
    if "flood" in normalized or "wait" in normalized or "spam" in normalized:
        return ErrorClass.FLOOD
    return ErrorClass.UNKNOWN

