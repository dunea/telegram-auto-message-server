from pydantic import BaseModel, Field


class ReplyMessageMediaItem(BaseModel):
    """回复消息媒体项。"""

    file_record_id: int | None = None
    sort_order: int = 0


class ReplyMessageCreate(BaseModel):
    """创建回复消息请求。"""

    text: str = Field(default="", max_length=100000)
    sort_order: int = 0
    media: list[ReplyMessageMediaItem] = []


class ReplyMessageUpdate(BaseModel):
    """更新回复消息请求。"""

    text: str | None = Field(default=None, max_length=100000)
    sort_order: int | None = None


class ReplyMessageResponse(BaseModel):
    """回复消息响应。"""

    id: int
    rule_id: int
    text: str
    sort_order: int
    media: list[ReplyMessageMediaItem] = []
