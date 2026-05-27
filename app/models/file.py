from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FileRecord(Base, TimestampMixin):
    """文件记录：本地临时文件到 S3 的生命周期。"""

    __tablename__ = "file_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    local_path: Mapped[str] = mapped_column(String(512), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    s3_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
