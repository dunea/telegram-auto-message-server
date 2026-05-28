from pydantic import BaseModel, Field

from app.schema.message import MessageContentInput


class CreateScheduledTaskRequest(BaseModel):
    """创建定时任务请求。"""

    account_id: int
    cron_expr: str = Field(..., min_length=3, max_length=64)
    target_identifier: str
    message_content: MessageContentInput | None = None
    message_template: str = Field(default="", max_length=100000)


class CreateRuleTaskRequest(BaseModel):
    """创建规则任务请求。"""

    account_id: int
    trigger_type: str
    condition_json: str
    action_json: str
    message_content: MessageContentInput | None = None
    message_template: str = Field(default="", max_length=100000)
