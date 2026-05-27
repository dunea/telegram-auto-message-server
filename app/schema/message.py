from pydantic import BaseModel


class SendMessageRequest(BaseModel):
    account_id: int
    target_identifier: str
    content: str


class SendMessageResult(BaseModel):
    account_id: int
    target_identifier: str
    content: str
    status: str
    telegram_message_id: int | None = None
    error: str | None = None
