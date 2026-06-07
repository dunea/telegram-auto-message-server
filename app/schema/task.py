from pydantic import BaseModel, Field

from app.schema.message import MessageContentInput


class CreateScheduledTaskRequest(BaseModel):
    """创建定时任务请求。"""

    account_id: int
    cron_expr: str = Field(..., min_length=3, max_length=64)
    target_identifier: str
    message_content: MessageContentInput | None = None
    message_template: str = Field(default="", max_length=100000)
    scope_mode: str = Field(default="all", max_length=20)
    conversation_ids: list[int] | None = None
    message_ids: list[int] | None = None


class CreateRuleTaskRequest(BaseModel):
    """创建规则任务请求。"""

    account_id: int
    trigger_type: str
    condition_json: str
    action_json: str
    message_content: MessageContentInput | None = None
    message_template: str = Field(default="", max_length=100000)
    scope_mode: str = Field(default="all", max_length=20)
    conversation_ids: list[int] | None = None
    message_ids: list[int] | None = None


class UpdateScheduledTaskRequest(BaseModel):
    """更新定时消息任务请求。"""

    cron_expr: str = Field(..., min_length=3, max_length=64)
    target_identifier: str = Field(..., min_length=1, max_length=255)
    message_content: MessageContentInput | None = None
    message_template: str = Field(default="", max_length=100000)
    scope_mode: str | None = Field(default=None, max_length=20)
    conversation_ids: list[int] | None = None
    message_ids: list[int] | None = None


class UpdateTaskActiveRequest(BaseModel):
    """任务启停请求。"""

    is_active: bool


class ScheduledTaskResponse(BaseModel):
    """定时消息任务响应。"""

    task_id: int
    account_id: int
    cron_expr: str
    target_identifier: str
    message_template: str
    message_content_id: int | None = None
    is_active: bool
    scope_mode: str = "all"
    conversation_ids: list[int] | None = None
    message_ids: list[int] | None = None


class ScheduledTaskListResponse(BaseModel):
    """定时消息列表响应。"""

    total: int
    items: list[ScheduledTaskResponse]
