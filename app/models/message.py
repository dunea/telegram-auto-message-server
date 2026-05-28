from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import (
    MessageAttemptStatus,
    MessageContentType,
    MessageDirection,
    MessageMediaType,
    MessageSendStatus,
    MessageSourceType,
    TelegramPeerType,
)


class MessageContent(Base, TimestampMixin):
    """消息模板主表，承载可发送内容的文本与摘要信息。"""

    __tablename__ = "message_content"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键 ID"
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="所属账号 ID"
    )
    content_type: Mapped[MessageContentType] = mapped_column(
        String(16),
        nullable=False,
        default=MessageContentType.TEXT,
        comment="消息内容类型（text/media/emoji）",
    )
    text_content: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None, comment="文本内容"
    )
    media_type: Mapped[MessageMediaType | None] = mapped_column(
        String(32),
        nullable=True,
        default=None,
        comment="媒体类型（image/video/audio/file/sticker）",
    )
    media_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, default=None, comment="媒体 URL"
    )
    media_key: Mapped[str | None] = mapped_column(
        String(512), nullable=True, default=None, comment="媒体对象 Key"
    )
    emoji: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None, comment="表情内容"
    )
    caption: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None, comment="媒体说明或补充文案"
    )
    extra_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}", comment="扩展 JSON"
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, nullable=False, comment="内容启用状态"
    )


class MessageContentMedia(Base, TimestampMixin):
    """消息模板媒体明细，一条模板可关联多个媒体/文件。"""

    __tablename__ = "message_content_media"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键 ID"
    )
    message_content_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="关联消息模板 ID"
    )
    media_type: Mapped[MessageMediaType] = mapped_column(
        String(32),
        nullable=False,
        default=MessageMediaType.FILE,
        comment="媒体类型（image/video/audio/file/sticker）",
    )
    media_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, default=None, comment="媒体 URL"
    )
    media_key: Mapped[str | None] = mapped_column(
        String(512), nullable=True, default=None, comment="媒体对象 Key"
    )
    caption: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None, comment="单媒体说明"
    )
    sort_order: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="排序号"
    )


class TelegramMessage(Base, TimestampMixin):
    """Telegram 会话完整消息记录（入站 + 出站）。"""

    __tablename__ = "telegram_message"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键 ID"
    )
    message_content_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="关联消息内容 ID"
    )
    source_type: Mapped[MessageSourceType] = mapped_column(
        String(16),
        nullable=False,
        default=MessageSourceType.MANUAL,
        comment="消息来源类型（manual/scheduled/rule/auto_reply）",
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="托管账号 ID"
    )
    conversation_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="会话 ID"
    )
    conversation_peer: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="会话可读标识"
    )
    grouped_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Telegram 消息组 ID（相册/媒体组）"
    )
    group_index: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="同组消息排序"
    )
    peer_type: Mapped[TelegramPeerType] = mapped_column(
        String(16),
        nullable=False,
        default=TelegramPeerType.UNKNOWN,
        comment="会话类型（user/chat/channel/unknown）",
    )
    peer_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="会话对象 ID"
    )
    sender_telegram_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="发送者 Telegram 用户 ID"
    )
    direction: Mapped[MessageDirection] = mapped_column(
        String(16),
        nullable=False,
        default=MessageDirection.OUT,
        comment="消息方向（out/in）",
    )
    content_type: Mapped[MessageContentType] = mapped_column(
        String(16),
        nullable=False,
        default=MessageContentType.TEXT,
        comment="消息内容类型（text/media/emoji）",
    )
    text_content: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None, comment="文本内容"
    )
    media_type: Mapped[MessageMediaType | None] = mapped_column(
        String(32), nullable=True, default=None, comment="媒体类型"
    )
    media_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, default=None, comment="媒体 URL"
    )
    media_key: Mapped[str | None] = mapped_column(
        String(512), nullable=True, default=None, comment="媒体对象 Key"
    )
    emoji: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None, comment="表情内容"
    )
    status: Mapped[MessageSendStatus] = mapped_column(
        String(32),
        nullable=False,
        default=MessageSendStatus.PENDING,
        comment="消息状态（pending/sent/failed）",
    )
    telegram_message_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Telegram 消息 ID"
    )
    reply_to_telegram_message_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="回复的 Telegram 消息 ID"
    )
    forward_from_telegram_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="转发来源 Telegram 用户 ID"
    )
    source_message_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="回复/转发来源消息 ID"
    )
    task_execution_log_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="关联任务执行日志 ID"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None, comment="错误信息"
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="消息发送时间"
    )
    message_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="消息时间（入站为接收时间，出站为发送时间）",
    )


class TelegramMessageMedia(Base, TimestampMixin):
    """会话消息媒体明细，一条会话消息可挂多条媒体。"""

    __tablename__ = "telegram_message_media"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键 ID"
    )
    telegram_message_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="关联会话消息 ID"
    )
    grouped_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Telegram 消息组 ID"
    )
    media_type: Mapped[MessageMediaType] = mapped_column(
        String(32),
        nullable=False,
        default=MessageMediaType.FILE,
        comment="媒体类型（image/video/audio/file/sticker）",
    )
    media_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, default=None, comment="媒体 URL"
    )
    media_key: Mapped[str | None] = mapped_column(
        String(512), nullable=True, default=None, comment="媒体对象 Key"
    )
    caption: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None, comment="单媒体说明"
    )
    telegram_media_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default=None, comment="Telegram 媒体 ID"
    )
    sort_order: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="排序号"
    )


class TelegramMessageSendAttempt(Base, TimestampMixin):
    """消息发送尝试日志，一条出站消息可有多次发送尝试。"""

    __tablename__ = "telegram_message_send_attempt"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键 ID"
    )
    telegram_message_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="关联会话消息 ID"
    )
    attempt_no: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, comment="尝试序号，从 1 开始"
    )
    status: Mapped[MessageAttemptStatus] = mapped_column(
        String(16),
        nullable=False,
        default=MessageAttemptStatus.SENDING,
        comment="尝试状态（sending/sent/failed）",
    )
    telegram_message_id_value: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="本次尝试返回的 Telegram 消息 ID"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None, comment="本次尝试错误信息"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="尝试开始时间"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="尝试结束时间"
    )
    duration_ms: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="尝试耗时毫秒"
    )
