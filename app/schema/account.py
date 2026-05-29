from pydantic import BaseModel, Field


class CreateAccountRequest(BaseModel):
    """新增托管账号请求。"""

    phone_number: str = Field(..., min_length=3, max_length=64)
    proxy_id: int | None = None
    session_string: str | None = None


class CreateAccountWithSessionRequest(BaseModel):
    """通过 session 登录并托管账号请求。"""

    phone_number: str = Field(..., min_length=3, max_length=64)
    session_string: str = Field(..., min_length=16, max_length=4096)
    proxy_id: int | None = None


class RequestPhoneLoginCodeRequest(BaseModel):
    """请求手机号验证码。"""

    phone_number: str = Field(..., min_length=3, max_length=64)
    proxy_id: int | None = None


class VerifyPhoneCodeRequest(BaseModel):
    """提交短信验证码。"""

    phone_code_hash: str = Field(..., min_length=6, max_length=256)
    code: str = Field(..., min_length=3, max_length=32)


class VerifyTwoFactorPasswordRequest(BaseModel):
    """提交二级密码。"""

    password: str = Field(..., min_length=1, max_length=256)


class UpdateAccountActiveRequest(BaseModel):
    """账号启停请求。"""

    is_active: bool


class LoginStepResponse(BaseModel):
    """账号登录步骤响应。"""

    account_id: int
    phone_number: str
    is_active: bool
    is_online: bool
    next_step: str
    message: str
    phone_code_hash: str | None = None


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
