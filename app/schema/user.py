from pydantic import BaseModel, Field


class RegisterUserRequest(BaseModel):
    """用户注册请求。"""

    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class LoginUserRequest(BaseModel):
    """用户登录请求。"""

    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class AccessTokenResponse(BaseModel):
    """登录访问令牌响应。"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class RefreshTokenRequest(BaseModel):
    """刷新访问令牌请求。"""

    refresh_token: str = Field(..., min_length=16, max_length=4096)


class UserProfileResponse(BaseModel):
    """当前用户信息响应。"""

    user_id: int
    email: str
    is_active: bool
