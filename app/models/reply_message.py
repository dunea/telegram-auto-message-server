from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import TYPE_CHECKING

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.task import AutoReplyRule
    from app.models.reply_message_media import ReplyMessageMedia


class ReplyMessage(Base, TimestampMixin):
    __tablename__ = "reply_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("auto_reply_rule.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(BigInteger, default=0)

    rule: Mapped["AutoReplyRule"] = relationship(
        "AutoReplyRule", back_populates="reply_messages"
    )
    media: Mapped[list["ReplyMessageMedia"]] = relationship(
        "ReplyMessageMedia", back_populates="reply_message",
        cascade="all, delete-orphan"
    )
