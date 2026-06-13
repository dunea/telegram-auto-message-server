from enum import Enum


class StrEnum(str, Enum):
    """字符串枚举基类。"""

    def __str__(self) -> str:  # pragma: no cover - 仅用于显示
        return str(self.value)


class MessageContentType(StrEnum):
    """消息内容类型。"""

    TEXT = "text"
    MEDIA = "media"
    EMOJI = "emoji"


class MessageMediaType(StrEnum):
    """消息媒体类型。"""

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    STICKER = "sticker"


class MessageDirection(StrEnum):
    """消息方向。"""

    OUT = "out"
    IN = "in"


class MessageSendStatus(StrEnum):
    """消息发送状态。"""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class MessageAttemptStatus(StrEnum):
    """单次发送尝试状态。"""

    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


class MessageSourceType(StrEnum):
    """消息来源类型。"""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    RULE = "rule"
    AUTO_REPLY = "auto_reply"


class ErrorClass(StrEnum):
    """运行时错误分类。"""

    NONE = "none"
    TIMEOUT = "timeout"
    AUTH = "auth"
    NETWORK = "network"
    FLOOD = "flood"
    UNKNOWN = "unknown"


class TelegramPeerType(StrEnum):
    """Telegram 会话对象类型。"""

    USER = "user"
    CHAT = "chat"
    CHANNEL = "channel"
    UNKNOWN = "unknown"


class TaskExecutionStatus(StrEnum):
    """任务执行状态。"""

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
