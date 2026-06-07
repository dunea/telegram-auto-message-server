from pydantic import BaseModel, Field

from app.schema.reply_message import ReplyMessageCreate, ReplyMessageResponse


class CreateAutoReplyRuleRequest(BaseModel):
    """新增自动回复规则请求。"""

    account_id: int
    trigger_keyword: str = Field(..., min_length=1, max_length=255)
    reply_content: str = Field(..., min_length=1, max_length=100000)
    trigger_mode: str = Field(default="keyword", max_length=20)
    keywords: list[str] | None = None
    scope_mode: str = Field(default="all", max_length=20)
    conversation_ids: list[int] | None = None
    reply_messages: list[ReplyMessageCreate] = []


class UpdateAutoReplyRuleRequest(BaseModel):
    """更新自动回复规则请求。"""

    trigger_keyword: str | None = Field(default=None, min_length=1, max_length=255)
    reply_content: str | None = Field(default=None, min_length=1, max_length=100000)
    trigger_mode: str | None = Field(default=None, max_length=20)
    keywords: list[str] | None = None
    scope_mode: str | None = Field(default=None, max_length=20)
    conversation_ids: list[int] | None = None
    reply_messages: list[ReplyMessageCreate] | None = None


class UpdateAutoReplyRuleActiveRequest(BaseModel):
    """自动回复规则启停请求。"""

    is_active: bool


class AutoReplyRuleResponse(BaseModel):
    """自动回复规则响应。"""

    rule_id: int
    account_id: int
    trigger_keyword: str
    reply_content: str
    is_active: bool
    trigger_mode: str
    keywords: list[str] | None = None
    scope_mode: str
    conversation_ids: list[int] | None = None
    reply_messages: list[ReplyMessageResponse] = []


class AutoReplyRuleListResponse(BaseModel):
    """自动回复规则列表响应。"""

    total: int
    items: list[AutoReplyRuleResponse]
