import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import BigInteger

from app.models.base import Base
from app.models.account import TelegramAccount
from app.models.task import AutoReplyRule
from app.models.message import TelegramMessage
from app.worker.pool_runner import PoolRunner
from app.config import Settings

@compiles(BigInteger, "sqlite")
def compile_bigint_sqlite(type_, compiler, **kw):
    return "INTEGER"

@pytest.mark.anyio
async def test_pool_runner_auto_reply_flow() -> None:
    # 1. 创建内存异步数据库引擎
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    # 2. 创建所有数据表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        # 3. 写入测试初始数据
        async with session_factory() as session:
            # 创建托管的 Telegram 账号
            account = TelegramAccount(
                id=1,
                phone_number="+1234567890",
                session_string="fake_session",
                telegram_user_id=11111,
                is_active=True,
                is_online=True,
            )
            session.add(account)

            # 创建自动回复规则
            rule = AutoReplyRule(
                id=1,
                account_id=1,
                trigger_mode="keyword",
                trigger_keyword="hello",
                reply_content="world",
                scope_mode="all",
                is_active=True,
            )
            session.add(rule)
            await session.commit()

        # 4. 配置 Settings 与创建 PoolRunner
        settings = Settings(
            jwt_secret_key="unit-test-secret",
            pool_total_shards=1,
            pool_shard_index=0,
            pool_max_concurrent_logins=1,
        )

        runner = PoolRunner(settings=settings)
        # 覆盖 session_factory 以连到内存数据库
        runner._session_factory = session_factory

        # Mock 适配器的发送方法，假装发送成功
        runner._telegram_adapter.SendMessage = AsyncMock(
            return_value={
                "message_id": 99999,
                "target_identifier": "22222",
                "content": "world",
                "date": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                "peer_type": "user",
                "peer_id": 22222,
                "sender_id": 11111,
                "status": "sent",
            }
        )

        # 5. 构造模拟的 Telethon 消息接收事件 (events.NewMessage)
        fake_peer = MagicMock()
        fake_peer.user_id = 22222

        fake_message = MagicMock()
        fake_message.id = 12345
        fake_message.message = "  hello there  "
        fake_message.peer_id = fake_peer
        fake_message.sender_id = 22222
        fake_message.date = datetime.now(timezone.utc).replace(tzinfo=None)
        fake_message.reply_to = None
        fake_message.grouped_id = None

        fake_event = MagicMock()
        fake_event.message = fake_message

        # 6. 执行非同步事件回调
        await runner._handle_incoming_message(account_id=1, event=fake_event)

        # 7. 断言验证
        # 验证是否调用了适配器发送 "world" 回复给 "22222"
        runner._telegram_adapter.SendMessage.assert_awaited_once_with(
            account_id=1,
            session_string="fake_session",
            target_identifier="22222",
            content="world",
        )

        # 验证接收到的消息与自动发送的回复是否都在数据库成功归档
        async with session_factory() as session:
            from sqlalchemy import select
            messages = (await session.execute(select(TelegramMessage))).scalars().all()

            # 应存在两条消息记录：一收（IN），一发（OUT）
            assert len(messages) == 2

            incoming = next(m for m in messages if m.direction == "in")
            assert incoming.text_content == "hello there"
            assert incoming.telegram_message_id == 12345
            assert incoming.conversation_peer == "22222"

            outgoing = next(m for m in messages if m.direction == "out")
            assert outgoing.text_content == "world"
            assert outgoing.conversation_peer == "22222"
            assert outgoing.source_type == "auto_reply"

    finally:
        await engine.dispose()
