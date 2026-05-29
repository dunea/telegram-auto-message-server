"""用户注册、登录与鉴权信息 API 路由。"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_auth_service, get_current_user
from app.models.user import User
from app.schema.user import AccessTokenResponse, LoginUserRequest, RefreshTokenRequest, RegisterUserRequest, UserProfileResponse
from app.service.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserProfileResponse)
def register_user(
    payload: RegisterUserRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserProfileResponse:
    """注册新用户。"""
    try:
        result = auth_service.RegisterUser(email=payload.email, password=payload.password)
        return UserProfileResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/login", response_model=AccessTokenResponse)
def login_user(
    payload: LoginUserRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AccessTokenResponse:
    """用户登录并获取访问令牌。"""
    try:
        result = auth_service.LoginUser(email=payload.email, password=payload.password)
        return AccessTokenResponse(**result)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/refresh-token", response_model=AccessTokenResponse)
def refresh_access_token(
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AccessTokenResponse:
    """使用 refresh token 刷新 access token，并轮换 refresh token。"""
    try:
        result = auth_service.RefreshAccessToken(refresh_token=payload.refresh_token)
        return AccessTokenResponse(**result)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/me")
def get_service_user_profile(current_user: User = Depends(get_current_user)) -> UserProfileResponse:
    """获取当前登录用户信息。"""
    return UserProfileResponse(
        user_id=int(current_user.id),
        email=str(current_user.email),
        is_active=bool(current_user.is_active),
    )
