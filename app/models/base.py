from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """ORM 声明式基类，统一承载模型元数据注册入口。"""


class TimestampMixin:
    """通用时间字段混入，提供创建时间与更新时间的自动维护能力。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="记录创建时间（数据库服务器时间）",
    )
    # 数据库在更新记录时自动刷新该字段。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="记录最后更新时间（数据库服务器时间）",
    )
