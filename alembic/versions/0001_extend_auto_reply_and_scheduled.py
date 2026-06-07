"""extend auto_reply and scheduled tables

Revision ID: 0001
Revises:
Create Date: 2026-06-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001"
# 注意: 这不是第一个迁移，base 表 (auto_reply_rule, scheduled_message_task, file_record 等)
# 已存在于生产环境，本迁移只做扩展 / 新增。
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. auto_reply_rule 新增4列
    op.add_column(
        "auto_reply_rule",
        sa.Column("trigger_mode", sa.String(20), nullable=False, server_default="keyword"),
    )
    op.add_column(
        "auto_reply_rule",
        sa.Column("keywords", sa.JSON(), nullable=True),
    )
    op.add_column(
        "auto_reply_rule",
        sa.Column("scope_mode", sa.String(20), nullable=False, server_default="all"),
    )
    op.add_column(
        "auto_reply_rule",
        sa.Column("conversation_ids", sa.JSON(), nullable=True),
    )

    # 2. 新建 reply_message 表
    op.create_table(
        "reply_message",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reply_message_rule_id"), "reply_message", ["rule_id"]
    )
    op.create_foreign_key(
        op.f("fk_reply_message_rule_id_auto_reply_rule"),
        "reply_message",
        "auto_reply_rule",
        ["rule_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 3. 新建 reply_message_media 表
    op.create_table(
        "reply_message_media",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("reply_message_id", sa.BigInteger(), nullable=False),
        sa.Column("file_record_id", sa.BigInteger(), nullable=True),
        sa.Column("sort_order", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reply_message_media_reply_message_id"),
        "reply_message_media",
        ["reply_message_id"],
    )
    op.create_foreign_key(
        op.f("fk_reply_message_media_reply_message_id_reply_message"),
        "reply_message_media",
        "reply_message",
        ["reply_message_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_reply_message_media_file_record_id_file_record"),
        "reply_message_media",
        "file_record",
        ["file_record_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 4. scheduled_message_task 新增3列
    op.add_column(
        "scheduled_message_task",
        sa.Column("scope_mode", sa.String(20), nullable=False, server_default="all"),
    )
    op.add_column(
        "scheduled_message_task",
        sa.Column("conversation_ids", sa.JSON(), nullable=True),
    )
    op.add_column(
        "scheduled_message_task",
        sa.Column("message_ids", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    # 4. scheduled_message_task 回退3列
    op.drop_column("scheduled_message_task", "message_ids")
    op.drop_column("scheduled_message_task", "conversation_ids")
    op.drop_column("scheduled_message_task", "scope_mode")

    # 3. reply_message_media 回退
    op.drop_constraint(
        op.f("fk_reply_message_media_file_record_id_file_record"),
        "reply_message_media",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_reply_message_media_reply_message_id_reply_message"),
        "reply_message_media",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_reply_message_media_reply_message_id"),
        table_name="reply_message_media",
    )
    op.drop_table("reply_message_media")

    # 2. reply_message 回退
    op.drop_constraint(
        op.f("fk_reply_message_rule_id_auto_reply_rule"),
        "reply_message",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_reply_message_rule_id"), table_name="reply_message"
    )
    op.drop_table("reply_message")

    # 1. auto_reply_rule 回退4列
    op.drop_column("auto_reply_rule", "conversation_ids")
    op.drop_column("auto_reply_rule", "scope_mode")
    op.drop_column("auto_reply_rule", "keywords")
    op.drop_column("auto_reply_rule", "trigger_mode")
