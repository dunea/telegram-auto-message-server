from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FileRecord(Base, TimestampMixin):
    """文件生命周期记录模型，用于管理本地临时文件与 S3 上传状态。"""

    __tablename__ = "file_record"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键 ID"
    )
    local_path: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="本地临时文件路径"
    )
    s3_key: Mapped[str | None] = mapped_column(
        String(512), nullable=True, default=None, comment="S3 对象 Key"
    )
    s3_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, default=None, comment="S3 访问 URL"
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="文件大小（字节）"
    )
    # 固定枚举：pending=待上传，uploaded=已上传，deleted=已清理。
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", comment="文件生命周期状态"
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="文件过期时间"
    )
    owner_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, default=None, comment="归属用户 ID"
    )

