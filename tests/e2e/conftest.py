"""E2E fixture 改造为 async（PR #11 收尾后）。

说明：之前 fixture 用 sync session_factory + sync AuthService，PR #11 收尾后
全链路 async，需用 async session_factory + async AuthService。
"""
import asyncio
import threading
import time
import uvicorn
import pytest
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import BigInteger

from app.config import get_settings
from app.startup import create_api_application
from app.api.deps import get_session_factory
from app.service.auth_service import AuthService
from app.repository.user_repository import SqlAlchemyUserRepository
from app.models.base import Base


@compiles(BigInteger, "sqlite")
def compile_bigint_sqlite(type_, compiler, **kw):
    return "INTEGER"


@pytest.fixture(scope="session", autouse=True)
def init_e2e_database():
    session_factory = get_session_factory()
    engine = session_factory.kw["bind"]

    # 导入模型确保在 metadata 中注册
    from app.models.user import User
    from app.models.account import TelegramAccount
    from app.models.task import AutoReplyRule, ScheduledMessageTask
    from app.models.message import TelegramMessage
    from app.models.reply_message import ReplyMessage
    from app.models.file import FileRecord

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())
    yield


@pytest.fixture(scope="session")
def server_url(init_e2e_database):
    settings = get_settings()
    host = "127.0.0.1"
    port = 8099
    app = create_api_application(settings)

    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()

    time.sleep(1.0)
    yield f"http://{host}:{port}"

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def e2e_user(server_url):
    session_factory = get_session_factory()

    async def _register():
        async with session_factory() as session:
            settings = get_settings()
            user_repo = SqlAlchemyUserRepository(session)
            auth_service = AuthService(settings, session, user_repo)
            email = "e2e_test@example.com"
            password = "password123"
            if not await user_repo.ExistsByEmail(email):
                await auth_service.RegisterUser(email=email, password=password)
            return {"email": email, "password": password}

    return asyncio.run(_register())
