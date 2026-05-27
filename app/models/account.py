from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TelegramAccount(Base, TimestampMixin):
    """托管 Telegram 账号。"""

    __tablename__ = "telegram_account"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    phone_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    session_string: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    proxy_id: Mapped[int] = mapped_column(BigInteger, nullable=True)


class ProxyInfo(Base, TimestampMixin):
    """代理 IP 信息。"""

    __tablename__ = "proxy_info"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    proxy_host: Mapped[str] = mapped_column(String(255), nullable=False)
    proxy_port: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    password: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
