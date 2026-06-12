from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """API 调用方用户模型，维护认证身份与鉴权凭证。"""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键 ID"
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, comment="用户登录邮箱"
    )
    # 仅存储密码哈希，禁止写入明文密码。
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希"
    )
    api_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, comment="API 鉴权 Key"
    )
    # 禁用后禁止登录与接口调用。
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="用户启用状态"
    )
    # True 表示管理员，False 表示普通用户，默认为普通用户。
    is_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否为管理员"
    )
