from pydantic import BaseModel, Field


class CreateScheduledTaskRequest(BaseModel):
    account_id: int
    cron_expr: str = Field(..., min_length=3, max_length=64)
    target_identifier: str
    message_template: str


class CreateRuleTaskRequest(BaseModel):
    account_id: int
    trigger_type: str
    condition_json: str
    action_json: str
