"""Web 认证路由与页面渲染单元测试。"""

import jwt
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.api.deps import get_auth_service
from app.config import get_settings
from app.web.routes.auth import router as auth_router


class FakeAuthServiceForWeb:
    """用于 Web 认证路由测试的伪认证服务。"""

    async def RegisterUser(self, email: str, password: str) -> dict:
        if email == "exist@example.com":
            raise ValueError("邮箱已注册")
        return {"user_id": 1, "email": email, "is_active": True}

    async def LoginUser(self, email: str, password: str) -> dict:
        if email == "wrong@example.com":
            raise ValueError("邮箱或密码错误")
        return {
            "access_token": "fake-web-access-token",
            "refresh_token": "fake-web-refresh-token",
            "token_type": "bearer",
            "expires_in_seconds": 3600,
        }


def _build_web_client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthServiceForWeb()
    return TestClient(app)


def test_login_page_get_not_logged_in() -> None:
    client = _build_web_client()
    resp = client.get("/web/login")
    assert resp.status_code == 200
    assert "登录" in resp.text
    assert "电子邮箱" in resp.text


def test_login_page_get_already_logged_in() -> None:
    client = _build_web_client()
    settings = get_settings()
    token = jwt.encode(
        {"sub": "123", "email": "test@example.com"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    client.cookies.set("web_token", token)
    resp = client.get("/web/login", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/dashboard"


def test_login_post_success() -> None:
    client = _build_web_client()
    resp = client.post(
        "/web/login",
        data={"email": "test@example.com", "password": "Password123"},
        follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/dashboard"
    assert "web_token" in resp.cookies
    assert resp.cookies["web_token"] == "fake-web-access-token"


def test_login_post_failure() -> None:
    client = _build_web_client()
    resp = client.post(
        "/web/login",
        data={"email": "wrong@example.com", "password": "Password123"}
    )
    assert resp.status_code == 200
    assert "邮箱或密码错误" in resp.text


def test_register_page_get_not_logged_in() -> None:
    client = _build_web_client()
    resp = client.get("/web/register")
    assert resp.status_code == 200
    assert "注册新账户" in resp.text


def test_register_page_get_already_logged_in() -> None:
    client = _build_web_client()
    settings = get_settings()
    token = jwt.encode(
        {"sub": "123", "email": "test@example.com"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    client.cookies.set("web_token", token)
    resp = client.get("/web/register", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/dashboard"


def test_register_post_success() -> None:
    client = _build_web_client()
    resp = client.post(
        "/web/register",
        data={"email": "new@example.com", "password": "Password123"},
        follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/login?registered=true"


def test_register_post_failure() -> None:
    client = _build_web_client()
    resp = client.post(
        "/web/register",
        data={"email": "exist@example.com", "password": "Password123"}
    )
    assert resp.status_code == 200
    assert "邮箱已注册" in resp.text


def test_logout() -> None:
    client = _build_web_client()
    client.cookies.set("web_token", "fake-token")
    resp = client.post("/web/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/login"
    # Cookie should be deleted/expired (either absent or empty/expired)
    assert "web_token" not in resp.cookies or resp.cookies["web_token"] == ""
