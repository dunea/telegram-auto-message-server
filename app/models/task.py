from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import TaskExecutionStatus


class ScheduledMessageTask(Base, TimestampMixin):
    """定时发送任务模型，定义 Cron 触发的固定发送任务。"""

    __tablename__ = "scheduled_message_task"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键 ID"
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="执行账号 ID"
    )
    message_content_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="关联消息内容 ID")
    # 约定使用 5 或 6 段 Cron 表达式。
    cron_expr: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="Cron 定时表达式"
    )
    target_identifier: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="目标会话标识"
    )
    message_template: Mapped[str | None] = mapped_column(Text, nullable=True, default=None, comment="兼容旧版的文本模板")
    # 禁用后调度器不会装载该任务。
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="任务启用状态"
    )


class RuleMessageTask(Base, TimestampMixin):
    """规则触发发送任务模型，定义触发条件与执行动作。"""

    __tablename__ = "rule_message_task"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键 ID"
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="执行账号 ID"
    )
    message_content_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="关联消息内容 ID")
    trigger_type: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="规则触发类型"
    )
    # JSON 结构由业务层统一约定。
    condition_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}", comment="触发条件 JSON"
    )
    action_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}", comment="执行动作 JSON"
    )
    # 禁用后规则不参与匹配。
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="规则启用状态"
    )


class AutoReplyRule(Base, TimestampMixin):
    """自动回复规则模型，定义关键词触发的回复内容。"""

    __tablename__ = "auto_reply_rule"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键 ID"
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="所属账号 ID"
    )
    trigger_keyword: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="触发关键词"
    )
    reply_content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="自动回复内容"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="规则启用状态"
    )
    trigger_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="keyword", comment="触发模式: keyword|all"
    )
    keywords: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="关键词列表(JSON数组)"
    )
    scope_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="all", comment="会话范围: all|specific"
    )
    conversation_ids: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="指定会话ID列表(JSON数组)"
    )


class UserReplySample(Base, TimestampMixin):
    """用户回复样本模型，沉淀真实回复内容用于规则优化。"""

    __tablename__ = "user_reply_sample"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键 ID"
    )
    auto_reply_rule_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="自动回复规则 ID"
    )
    reply_content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="用户回复内容样本"
    )


class TaskExecutionLog(Base, TimestampMixin):
    """任务执行日志，记录一次任务触发、发送与结果。"""

    __tablename__ = "task_execution_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键 ID")
    task_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="任务类型（scheduled/rule）")
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="任务 ID")
    account_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="执行账号 ID")
    message_content_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="关联消息内容 ID")
    send_log_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="关联发送日志 ID")
    status: Mapped[TaskExecutionStatus] = mapped_column(
        String(16),
        nullable=False,
        default=TaskExecutionStatus.RUNNING,
        comment="执行状态（running/success/failed/skipped）",
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="结束时间")
    duration_ms: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="执行耗时毫秒")
    target_identifier: Mapped[str] = mapped_column(String(255), nullable=False, comment="目标会话标识")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None, comment="错误信息")
    shard_index: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="分片索引")
    total_shards: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, comment="分片总数")
