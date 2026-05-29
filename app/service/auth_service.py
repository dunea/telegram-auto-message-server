from datetime import datetime, timedelta, timezone
import uuid

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.user import User
from app.repository.user_repository import SqlAlchemyUserRepository


_PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """用户注册登录与 JWT 认证服务。"""

    def __init__(self, settings: Settings, session: Session, user_repository: SqlAlchemyUserRepository) -> None:
        self._settings = settings
        self._session = session
        self._user_repository = user_repository

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    def _build_access_token(self, user: User) -> tuple[str, int]:
        now = datetime.now(timezone.utc)
        expire_delta = timedelta(minutes=int(self._settings.jwt_access_token_expire_minutes))
        expire_at = now + expire_delta
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "iat": int(now.timestamp()),
            "exp": int(expire_at.timestamp()),
            "type": "access",
        }
        token = jwt.encode(payload, self._settings.jwt_secret_key, algorithm=self._settings.jwt_algorithm)
        return token, int(expire_delta.total_seconds())

    def _build_refresh_token(self, user: User) -> str:
        now = datetime.now(timezone.utc)
        expire_delta = timedelta(days=int(self._settings.jwt_refresh_token_expire_days))
        expire_at = now + expire_delta
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "iat": int(now.timestamp()),
            "exp": int(expire_at.timestamp()),
            "type": "refresh",
        }
        return jwt.encode(payload, self._settings.jwt_secret_key, algorithm=self._settings.jwt_algorithm)

    def _get_user_by_token(self, token: str, expected_type: str) -> User:
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret_key,
                algorithms=[self._settings.jwt_algorithm],
            )
        except InvalidTokenError as exc:
            raise ValueError("无效或过期的访问令牌") from exc

        token_type = str(payload.get("type") or "")
        if token_type != expected_type:
            raise ValueError("访问令牌类型不正确")

        user_id_raw = payload.get("sub")
        if user_id_raw is None:
            raise ValueError("访问令牌缺少用户信息")

        try:
            user_id = int(user_id_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("访问令牌用户信息非法") from exc

        user = self._user_repository.FindById(user_id)
        if user is None:
            raise ValueError("用户不存在")
        if not bool(user.is_active):
            raise PermissionError("用户已被禁用")
        return user

    def RegisterUser(self, email: str, password: str) -> dict:
        normalized_email = self._normalize_email(email)
        if "@" not in normalized_email:
            raise ValueError("邮箱格式不合法")
        if self._user_repository.ExistsByEmail(normalized_email):
            raise ValueError("邮箱已注册")

        password_hash = _PASSWORD_CONTEXT.hash(password)
        user = User(
            email=normalized_email,
            password_hash=password_hash,
            api_key=uuid.uuid4().hex,
            is_active=True,
        )
        self._user_repository.Save(user)
        self._session.commit()
        return {
            "user_id": int(user.id),
            "email": user.email,
            "is_active": bool(user.is_active),
        }

    def LoginUser(self, email: str, password: str) -> dict:
        normalized_email = self._normalize_email(email)
        user = self._user_repository.FindByEmail(normalized_email)
        if user is None:
            raise ValueError("邮箱或密码错误")
        if not bool(user.is_active):
            raise PermissionError("用户已被禁用")
        if not _PASSWORD_CONTEXT.verify(password, user.password_hash):
            raise ValueError("邮箱或密码错误")

        access_token, expires_in_seconds = self._build_access_token(user)
        refresh_token = self._build_refresh_token(user)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in_seconds": expires_in_seconds,
        }

    def RefreshAccessToken(self, refresh_token: str) -> dict:
        user = self._get_user_by_token(token=refresh_token, expected_type="refresh")
        access_token, expires_in_seconds = self._build_access_token(user)
        rotated_refresh_token = self._build_refresh_token(user)
        return {
            "access_token": access_token,
            "refresh_token": rotated_refresh_token,
            "token_type": "bearer",
            "expires_in_seconds": expires_in_seconds,
        }

    def GetCurrentUserByToken(self, token: str) -> User:
        return self._get_user_by_token(token=token, expected_type="access")
