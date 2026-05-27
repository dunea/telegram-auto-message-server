from sqlalchemy import BigInteger, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ScheduledMessageTask(Base, TimestampMixin):
    """定时发送任务。"""

    __tablename__ = "scheduled_message_task"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cron_expr: Mapped[str] = mapped_column(String(64), nullable=False)
    target_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    message_template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class RuleMessageTask(Base, TimestampMixin):
    """规则发送任务。"""

    __tablename__ = "rule_message_task"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False)
    condition_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    action_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AutoReplyRule(Base, TimestampMixin):
    """自动回复规则。"""

    __tablename__ = "auto_reply_rule"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    trigger_keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    reply_content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class UserReplySample(Base, TimestampMixin):
    """用户回复样本，用于自动回复学习。"""

    __tablename__ = "user_reply_sample"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    auto_reply_rule_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reply_content: Mapped[str] = mapped_column(Text, nullable=False)
