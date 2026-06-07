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

# 解决 SQLite 不支持 BigInteger 自增主键的问题，将其在 sqlite 方言下编译为 INTEGER
@compiles(BigInteger, 'sqlite')
def compile_bigint_sqlite(type_, compiler, **kw):
    return "INTEGER"

@pytest.fixture(scope="session", autouse=True)
def init_e2e_database():
    session_factory = get_session_factory()
    engine = session_factory.kw['bind']
    
    # 导入模型确保在 metadata 中注册
    from app.models.user import User
    from app.models.account import TelegramAccount
    from app.models.task import AutoReplyRule, ScheduledMessageTask
    from app.models.message import TelegramMessage
    from app.models.reply_message import ReplyMessage
    from app.models.file import FileRecord
    
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture(scope="session")
def server_url(init_e2e_database):
    settings = get_settings()
    host = "127.0.0.1"
    port = 8099  # 使用独立端口避免冲突
    app = create_api_application(settings)
    
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()
    
    time.sleep(1.0)  # 等待服务启动
    yield f"http://{host}:{port}"
    
    server.should_exit = True
    thread.join(timeout=5)

@pytest.fixture(scope="session")
def e2e_user(server_url):
    session_factory = get_session_factory()
    session = session_factory()
    try:
        settings = get_settings()
        user_repo = SqlAlchemyUserRepository(session)
        auth_service = AuthService(settings, session, user_repo)
        
        email = "e2e_test@example.com"
        password = "password123"
        if not user_repo.ExistsByEmail(email):
            auth_service.RegisterUser(email=email, password=password)
        session.commit()
        return {"email": email, "password": password}
    finally:
        session.close()
