from pydantic import BaseModel, Field


class CreateAccountRequest(BaseModel):
    """新增托管账号请求。"""

    phone_number: str = Field(..., min_length=3, max_length=64)
    proxy_id: int | None = None
    session_string: str | None = None


class AccountStatusResponse(BaseModel):
    account_id: int
    is_online: bool
    is_active: bool


class AccountOnlineRequest(BaseModel):
    session_string: str | None = None


class ConversationItemResponse(BaseModel):
    dialog_id: int
    title: str
    username: str
    unread_count: int
