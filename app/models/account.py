from datetime import datetime
from sqlalchemy import BigInteger, Boolean, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TelegramAccount(Base, TimestampMixin):
    """托管 Telegram 账号模型，存储账号身份、会话串与运行状态。"""

    __tablename__ = "telegram_account"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键 ID"
    )
    phone_number: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="Telegram 账号手机号（唯一）"
    )
    session_string: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        default=None,
        comment="Telethon 会话字符串",
    )
    telegram_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Telegram 平台用户 ID"
    )
    display_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None, comment="账号展示名称"
    )
    is_online: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="账号在线状态"
    )
    # 禁用后该账号不参与调度与巡检。
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True, nullable=False, comment="账号启用状态"
    )
    proxy_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="关联代理 ID"
    )
    api_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None, comment="账号自定义 Telegram API ID"
    )
    api_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None, comment="账号自定义 Telegram API Hash"
    )
    owner_user_id: Mapped[int | None] = mapped_column(
        BigInteger, index=True, nullable=True, default=None, comment="归属用户 ID"
    )
    claimed_by: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None, comment="当前认领此账号的号池实例 ID"
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None, comment="最后一次认领或续租的时间"
    )



class ProxyInfo(Base, TimestampMixin):
    """代理连接信息模型，为账号提供可复用的网络代理配置。"""

    __tablename__ = "proxy_info"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键 ID"
    )
    proxy_host: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="代理主机地址"
    )
    proxy_port: Mapped[int] = mapped_column(Integer, nullable=False, comment="代理端口")
    username: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default=None, comment="代理认证用户名"
    )
    password: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default=None, comment="代理认证密码"
    )
    proxy_type: Mapped[str] = mapped_column(
        String(50), default="socks5", server_default="socks5", nullable=False, comment="代理协议类型（socks5, socks4, http）"
    )
    # 禁用后该代理不再分配给账号使用。
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="代理启用状态"
    )


class InstanceHeartbeat(Base):
    """号池实例心跳表，用于多实例动态自适应分片。"""

    __tablename__ = "instance_heartbeat"

    instance_id: Mapped[str] = mapped_column(
        String(255), primary_key=True, comment="实例 ID"
    )
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="最后一次心跳时间"
    )
