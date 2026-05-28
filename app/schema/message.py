from pydantic import BaseModel, Field

from app.models.enums import MessageContentType, MessageMediaType, MessageSourceType


class MessageMediaItemInput(BaseModel):
    """单个媒体项。"""

    media_type: MessageMediaType = Field(default=MessageMediaType.FILE)
    media_url: str = Field(default="", max_length=1024)
    media_key: str = Field(default="", max_length=512)
    caption: str = Field(default="", max_length=100000)
    sort_order: int = Field(default=0, ge=0)


class MessageContentInput(BaseModel):
    """结构化消息内容。"""

    content_type: MessageContentType = Field(default=MessageContentType.TEXT)
    text_content: str = Field(default="", max_length=100000)
    media_type: MessageMediaType | None = None
    media_url: str = Field(default="", max_length=1024)
    media_key: str = Field(default="", max_length=512)
    emoji: str = Field(default="", max_length=64)
    caption: str = Field(default="", max_length=100000)
    media_items: list[MessageMediaItemInput] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    """发送消息请求。"""

    account_id: int
    target_identifier: str
    message_content: MessageContentInput | None = None
    content: str = Field(default="", max_length=100000)
    source_type: MessageSourceType = Field(default=MessageSourceType.MANUAL)


class SendMessageResult(BaseModel):
    """发送消息结果。"""

    account_id: int
    target_identifier: str
    content: str
    content_type: str
    status: str
    message_content_id: int | None = None
    send_log_id: int | None = None
    source_type: str = MessageSourceType.MANUAL.value
    telegram_message_id: int | None = None
    error: str | None = None
