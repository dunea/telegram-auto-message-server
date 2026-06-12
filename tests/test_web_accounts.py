"""账号管理页面与路由单元测试。"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session, get_telegram_service
from app.models.base import Base
from app.models.account import TelegramAccount, ProxyInfo
from app.web.dependencies import get_current_user_from_cookie
from app.web.routes.accounts import router as accounts_router

# 设置内存数据库，使用 StaticPool 确保所有连接共享同一个内存数据库
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


@pytest.fixture
def mock_telegram_service():
    service = MagicMock()
    service.RequestPhoneLoginCode = AsyncMock(return_value={
        "account_id": 42,
        "phone_code_hash": "dummy_hash",
        "message": "Sent"
    })
    service.VerifyPhoneLoginCode = AsyncMock(return_value={
        "account_id": 42,
        "next_step": "done"
    })
    service.VerifyTwoFactorPassword = AsyncMock(return_value={
        "account_id": 42,
        "next_step": "done"
    })
    service.CreateAccountWithSessionLogin = AsyncMock(return_value={
        "account_id": 42,
        "next_step": "done"
    })
    service.SoftDeleteAccount = AsyncMock(return_value={"account_id": 42, "deleted": True})
    service.EnsureAccountOnline = AsyncMock(return_value={"account_id": 42, "is_online": True})
    service.ListConversations = AsyncMock(return_value=[
        {"id": "conv_1", "title": "Test Group", "type": "group", "unread_count": 0}
    ])
    return service


@pytest.fixture
def client(mock_telegram_service):
    app = FastAPI()
    app.include_router(accounts_router)
    
    # 覆盖依赖
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    app.dependency_overrides[get_telegram_service] = lambda: mock_telegram_service
    
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_list_accounts_page(client) -> None:
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8613800001111", display_name="Test Account", is_active=True, is_online=True)
    db.add(acc)
    db.commit()
    db.close()
    
    response = client.get("/web/accounts")
    assert response.status_code == 200
    assert "+8613800001111" in response.text
    assert "Test Account" in response.text


def test_new_accounts_page(client) -> None:
    response = client.get("/web/accounts/new")
    assert response.status_code == 200
    assert "手机验证码登录" in response.text
    assert "直接导入 Session 字符串" in response.text


def test_request_phone_code(client, mock_telegram_service) -> None:
    response = client.post("/web/accounts/login/phone/request-code", data={
        "phone_number": "+8613800001111",
        "proxy_id": ""
    })
    assert response.status_code == 200
    assert "dummy_hash" in response.text
    mock_telegram_service.RequestPhoneLoginCode.assert_called_once_with("+8613800001111", proxy_id=None)


def test_verify_phone_code_done(client, mock_telegram_service) -> None:
    response = client.post("/web/accounts/42/login/phone/verify-code", data={
        "phone_code_hash": "dummy_hash",
        "code": "12345"
    })
    assert response.status_code == 200
    assert response.headers.get("HX-Redirect") == "/web/accounts"
    mock_telegram_service.VerifyPhoneLoginCode.assert_called_once_with(42, "dummy_hash", "12345")


def test_verify_phone_code_2fa(client, mock_telegram_service) -> None:
    mock_telegram_service.VerifyPhoneLoginCode = AsyncMock(return_value={
        "account_id": 42,
        "next_step": "verify_password"
    })
    response = client.post("/web/accounts/42/login/phone/verify-code", data={
        "phone_code_hash": "dummy_hash",
        "code": "12345"
    })
    assert response.status_code == 200
    assert "二级密码" in response.text


def test_verify_two_factor(client, mock_telegram_service) -> None:
    response = client.post("/web/accounts/42/login/phone/verify-password", data={
        "password": "mypassword"
    })
    assert response.status_code == 200
    assert response.headers.get("HX-Redirect") == "/web/accounts"
    mock_telegram_service.VerifyTwoFactorPassword.assert_called_once_with(42, "mypassword")


def test_login_with_session(client, mock_telegram_service) -> None:
    response = client.post("/web/accounts/login/session", data={
        "phone_number": "+8613800001111",
        "session_string": "dummy_session",
        "proxy_id": ""
    })
    assert response.status_code == 200
    assert response.headers.get("HX-Redirect") == "/web/accounts"
    mock_telegram_service.CreateAccountWithSessionLogin.assert_called_once_with("+8613800001111", "dummy_session", proxy_id=None)


def test_account_detail(client) -> None:
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8613800001111", display_name="Test Account", is_active=True, is_online=True)
    db.add(acc)
    db.commit()
    db.close()
    
    response = client.get("/web/accounts/1")
    assert response.status_code == 200
    assert "+8613800001111" in response.text
    assert "Test Group" in response.text


def test_toggle_active(client) -> None:
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8613800001111", is_active=True)
    db.add(acc)
    db.commit()
    db.close()
    
    response = client.post("/web/accounts/1/toggle-active")
    assert response.status_code == 200
    assert "已禁用" in response.text
    
    # 验证数据库状态是否翻转
    db = TestingSessionLocal()
    updated = db.get(TelegramAccount, 1)
    assert updated is not None
    assert updated.is_active is False
    db.close()


def test_delete_account_htmx(client, mock_telegram_service) -> None:
    # 含有 HX-Request 头部
    response = client.post("/web/accounts/42/delete", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert response.headers.get("HX-Redirect") == "/web/accounts"
    mock_telegram_service.SoftDeleteAccount.assert_called_once_with(42)


def test_delete_account_normal(client, mock_telegram_service) -> None:
    # 普通 POST 请求，应当 303 重定向
    response = client.post("/web/accounts/42/delete", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/web/accounts"


def test_online_account_htmx(client, mock_telegram_service) -> None:
    response = client.post("/web/accounts/42/online", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert response.headers.get("HX-Redirect") == "/web/accounts/42"
    mock_telegram_service.EnsureAccountOnline.assert_called_once_with(42)


def test_online_account_normal(client, mock_telegram_service) -> None:
    response = client.post("/web/accounts/42/online", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/web/accounts/42"
