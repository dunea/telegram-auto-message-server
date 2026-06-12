"""仪表盘页面与路由单元测试。"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session
from app.web.dependencies import get_current_user_from_cookie
from app.web.routes.dashboard import router as dashboard_router
from app.web import register_web_routes
from app.models.base import Base
from app.models.account import TelegramAccount
from app.models.task import AutoReplyRule, ScheduledMessageTask
from app.models.message import TelegramMessage

# 1. 设置内存数据库，使用 StaticPool 以确保所有连接共享同一个内存数据库
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class _FakeAsyncSession:
    """把 sync Session 包装为 async 兼容（PR #11 收尾后 web 测试用）。

    AsyncSession API 中只有部分方法是 async def（flush/scalar/scalars/get/execute/commit/refresh/delete），
    其余（add/add_all/expire/expire_all）是 sync。包装时区分。
    """
    def __init__(self, db):
        self._db = db
    def add(self, entity):
        return self._db.add(entity)
    def add_all(self, entities):
        return self._db.add_all(entities)
    def expire(self, *args, **kwargs):
        return self._db.expire(*args, **kwargs)
    def expire_all(self):
        return self._db.expire_all()
    async def flush(self):
        return self._db.flush()
    async def commit(self):
        return self._db.commit()
    async def refresh(self, *args, **kwargs):
        return self._db.refresh(*args, **kwargs)
    async def delete(self, *args, **kwargs):
        return self._db.delete(*args, **kwargs)
    async def execute(self, stmt):
        return self._db.execute(stmt)
    async def scalar(self, stmt):
        return self._db.scalar(stmt)
    async def scalars(self, stmt):
        return self._db.scalars(stmt)
    async def get(self, *args, **kwargs):
        return self._db.get(*args, **kwargs)


def get_testing_db():
    db = TestingSessionLocal()
    try:
        yield _FakeAsyncSession(db)
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前清空并重新创建表。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_root_redirects_to_dashboard() -> None:
    """测试访问 / 重定向到 /web/dashboard。"""
    app = FastAPI()
    register_web_routes(app)

    client = TestClient(app)
    resp = client.get("/", follow_redirects=False)

    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/dashboard"


def test_dashboard_unauthenticated() -> None:
    """测试未登录用户访问仪表盘，应该触发 HTTPException 并重定向至登录页。"""
    app = FastAPI()
    app.include_router(dashboard_router)
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    resp = client.get("/web/dashboard", follow_redirects=False)
    
    # 验证未登录时重定向
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/login"


def test_dashboard_authenticated_empty() -> None:
    """测试已登录用户访问空数据的仪表盘。"""
    app = FastAPI()
    app.include_router(dashboard_router)
    
    # 覆盖认证依赖，模拟已登录
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    resp = client.get("/web/dashboard")
    
    assert resp.status_code == 200
    assert "数据主页 & 仪表盘" in resp.text
    # 空数据状态下，“未发现托管账号”的提示应该被渲染
    assert "未发现托管账号" in resp.text


def test_dashboard_authenticated_with_data() -> None:
    """测试已登录用户访问包含数据的仪表盘，并检查统计数据和卡片。"""
    db = TestingSessionLocal()
    
    # 1. 注入账号数据，指定 id 避免 SQLite 的 BigInteger 自动递增主键冲突
    acc1 = TelegramAccount(id=1, phone_number="+8612345678901", is_active=True, is_online=True)
    acc2 = TelegramAccount(id=2, phone_number="+8612345678902", is_active=True, is_online=False)
    acc3 = TelegramAccount(id=3, phone_number="+8612345678903", is_active=False, is_online=False)
    db.add_all([acc1, acc2, acc3])
    
    # 2. 注入自动回复规则，指定 id
    rule1 = AutoReplyRule(id=1, account_id=1, trigger_keyword="hello", reply_content="world", is_active=True)
    rule2 = AutoReplyRule(id=2, account_id=1, trigger_keyword="hi", reply_content="hey", is_active=False)
    db.add_all([rule1, rule2])
    
    # 3. 注入定时任务，指定 id
    task1 = ScheduledMessageTask(id=1, account_id=1, cron_expr="* * * * *", target_identifier="chat1", is_active=True)
    task2 = ScheduledMessageTask(id=2, account_id=1, cron_expr="0 12 * * *", target_identifier="chat2", is_active=False)
    db.add_all([task1, task2])
    
    # 4. 注入消息（24小时出站消息），指定 id
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # 24h内：成功出站、失败出站、排队出站、入站消息
    msg_sent = TelegramMessage(id=1, account_id=1, conversation_peer="peer1", direction="out", status="sent", created_at=now - timedelta(hours=1))
    msg_failed = TelegramMessage(id=2, account_id=1, conversation_peer="peer2", direction="out", status="failed", created_at=now - timedelta(hours=2))
    msg_pending = TelegramMessage(id=3, account_id=1, conversation_peer="peer3", direction="out", status="pending", created_at=now - timedelta(hours=3))
    msg_in = TelegramMessage(id=4, account_id=1, conversation_peer="peer4", direction="in", status="sent", created_at=now - timedelta(hours=4))
    
    # 超过 24h 的消息（不应被统计）
    msg_old = TelegramMessage(id=5, account_id=1, conversation_peer="peer5", direction="out", status="sent", created_at=now - timedelta(hours=25))
    
    db.add_all([msg_sent, msg_failed, msg_pending, msg_in, msg_old])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(dashboard_router)
    
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    resp = client.get("/web/dashboard")
    
    assert resp.status_code == 200
    text = resp.text
    
    # 检查账号统计渲染
    assert "TG 账号托管" in text
    assert "1" in text  # 在线账号数量
    assert "/ 3" in text  # 总账号数量
    assert "已启用账号: 2" in text
    
    # 检查自动回复规则统计渲染
    assert "1" in text  # 活动中规则
    assert "/ 2" in text  # 总规则
    
    # 检查定时发送任务
    assert "1" in text  # 启用定时任务
    assert "/ 2" in text  # 总任务数
    
    # 检查 24h 出站消息统计
    assert "成功" in text
    assert "失败: 1" in text
    assert "排队: 1" in text
    
    # 应该不会显示“未发现托管账号”
    assert "未发现托管账号" not in text
