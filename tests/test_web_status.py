"""运行状态监控页面与路由单元测试。"""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session, get_task_scheduler
from app.web.dependencies import get_current_user_from_cookie
from app.web.routes.status import router as status_router
from app.models.base import Base
from app.models.account import TelegramAccount, ProxyInfo, InstanceHeartbeat

# 1. 设置内存数据库，使用 StaticPool 以确保所有连接共享同一个内存数据库
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class _FakeAsyncSession:
    """包装 sync Session 以适配 async db 依赖"""
    def __init__(self, db):
        self._db = db
    def add(self, entity):
        return self._db.add(entity)
    def add_all(self, entities):
        return self._db.add_all(entities)
    async def commit(self):
        return self._db.commit()
    async def execute(self, stmt):
        return self._db.execute(stmt)
    async def scalars(self, stmt):
        return self._db.scalars(stmt)


def get_testing_db():
    db = TestingSessionLocal()
    try:
        yield _FakeAsyncSession(db)
    finally:
        db.close()


class FakeScheduler:
    """模拟任务调度器"""
    running = True
    job_count = 2
    def GetJobIds(self):
        return ["job_id_1", "job_id_2"]


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前清空并重新创建表。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_status_page_unauthenticated() -> None:
    """测试未登录用户访问运行状态页面，应成功渲染 (200 OK) 而不是重定向。"""
    app = FastAPI()
    app.include_router(status_router)
    app.dependency_overrides[get_db_session] = get_testing_db
    app.dependency_overrides[get_task_scheduler] = lambda: FakeScheduler()
    
    client = TestClient(app)
    resp = client.get("/web/status", follow_redirects=False)
    
    assert resp.status_code == 200
    assert "运行状态监控" in resp.text


def test_status_page_authenticated_empty() -> None:
    """测试已登录用户访问，当数据库中无集群实例数据时的页面渲染。"""
    app = FastAPI()
    app.include_router(status_router)
    
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    app.dependency_overrides[get_task_scheduler] = lambda: FakeScheduler()
    
    client = TestClient(app)
    resp = client.get("/web/status")
    
    assert resp.status_code == 200
    text = resp.text
    assert "运行状态监控" in text
    assert "基础服务信息" in text
    assert "MySQL 数据库" in text
    assert "分布式号池与分片" in text
    assert "定时任务调度器" in text
    assert "暂无注册的集群实例心跳信息" in text
    assert "job_id_1" in text
    assert "job_id_2" in text


def test_status_page_authenticated_with_data() -> None:
    """测试包含托管账号、代理、消息成功率和集群实例心跳时运行状态页面的正确渲染。"""
    db = TestingSessionLocal()
    
    # 注入账号和代理数据
    acc1 = TelegramAccount(id=1, phone_number="+8618888888881", is_active=True, is_online=True)
    acc2 = TelegramAccount(id=2, phone_number="+8618888888882", is_active=False, is_online=False)
    db.add_all([acc1, acc2])
    
    proxy1 = ProxyInfo(id=1, proxy_host="127.0.0.1", proxy_port=1080, is_active=True)
    db.add(proxy1)
    
    # 注入集群心跳数据 (一个活跃，一个已失效)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    hb_active = InstanceHeartbeat(instance_id="instance-active-999", last_heartbeat=now - timedelta(seconds=10))
    hb_expired = InstanceHeartbeat(instance_id="instance-expired-888", last_heartbeat=now - timedelta(seconds=120))
    db.add_all([hb_active, hb_expired])
    
    # 注入 24h 内出站消息：1条成功，1条失败 (成功率应该是 50.0%)
    from app.models.message import TelegramMessage
    msg_ok = TelegramMessage(id=1, account_id=1, conversation_peer="peer1", direction="out", status="sent", created_at=now - timedelta(hours=2))
    msg_err = TelegramMessage(id=2, account_id=1, conversation_peer="peer2", direction="out", status="failed", created_at=now - timedelta(hours=3))
    db.add_all([msg_ok, msg_err])
    
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(status_router)
    
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    app.dependency_overrides[get_task_scheduler] = lambda: FakeScheduler()
    
    client = TestClient(app)
    resp = client.get("/web/status")
    
    assert resp.status_code == 200
    text = resp.text
    
    # 检查状态指示与健康显示
    assert "良好" in text or "运行良好" in text
    # 检查资源统计数据
    assert "1 / 2" in text  # 托管账号在线比例
    assert "1 / 1" in text  # 激活网络代理比例
    # 检查消息成功率
    assert "50.0%" in text
    assert "TOTAL_24H: 2" in text
    assert "SENT_24H: 1" in text
    # 检查心跳明细
    assert "instance-active-999" in text
    assert "instance-expired-888" in text
    assert "已失效" in text or "失效" in text
    # 检查 SEO 与技术原理文字渲染
    assert "技术架构原理与运行机制" in text
    assert "Telegram 多账号安全托管" in text
    assert "分片漂移防御机制" in text


def test_status_partial_authenticated() -> None:
    """测试已登录用户拉取 HTMX 局部刷新卡片。"""
    app = FastAPI()
    app.include_router(status_router)
    
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    app.dependency_overrides[get_task_scheduler] = lambda: FakeScheduler()
    
    client = TestClient(app)
    resp = client.get("/web/status/partial")
    
    assert resp.status_code == 200
    text = resp.text
    # 局部刷新不应该有完整的 HTML 骨架（例如没有 <!DOCTYPE html>，但会有卡片元素）
    assert "<!DOCTYPE html>" not in text
    assert "id=\"status-container\"" in text
    assert "LATEST REF:" in text
