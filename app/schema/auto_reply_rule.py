from pydantic import BaseModel, Field


class CreateAutoReplyRuleRequest(BaseModel):
    """新增自动回复规则请求。"""

    account_id: int
    trigger_keyword: str = Field(..., min_length=1, max_length=255)
    reply_content: str = Field(..., min_length=1, max_length=100000)


class UpdateAutoReplyRuleRequest(BaseModel):
    """更新自动回复规则请求。"""

    trigger_keyword: str = Field(..., min_length=1, max_length=255)
    reply_content: str = Field(..., min_length=1, max_length=100000)


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


class AutoReplyRuleListResponse(BaseModel):
    """自动回复规则列表响应。"""

    total: int
    items: list[AutoReplyRuleResponse]
