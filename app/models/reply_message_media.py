from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ReplyMessageMedia(Base, TimestampMixin):
    __tablename__ = "reply_message_media"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    reply_message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("reply_message.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    file_record_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("file_record.id", ondelete="SET NULL"),
        nullable=True
    )
    sort_order: Mapped[int] = mapped_column(BigInteger, default=0)

    reply_message: Mapped["ReplyMessage"] = relationship(
        "ReplyMessage", back_populates="media"
    )
