"""鉴权测试：注册、登录、用户信息与受保护接口访问。"""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_auth_service, get_current_user
from app.api.router import build_api_router


class FakeAuthService:
    """用于 users 路由测试的伪认证服务。"""

    def RegisterUser(self, email: str, password: str) -> dict:
        _ = password
        return {
            "user_id": 1,
            "email": email,
            "is_active": True,
        }

    def LoginUser(self, email: str, password: str) -> dict:
        _ = (email, password)
        return {
            "access_token": "fake-access-token",
            "refresh_token": "fake-refresh-token",
            "token_type": "bearer",
            "expires_in_seconds": 3600,
        }

    def RefreshAccessToken(self, refresh_token: str) -> dict:
        if refresh_token == "bad-refresh-token":
            raise ValueError("无效或过期的访问令牌")
        return {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "token_type": "bearer",
            "expires_in_seconds": 3600,
        }


def _build_client_for_user_routes() -> TestClient:
    app = FastAPI()
    app.include_router(build_api_router())
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, email="demo@example.com", is_active=True)
    return TestClient(app)


def test_register_login_me_success() -> None:
    client = _build_client_for_user_routes()

    register_resp = client.post(
        "/api/v1/users/register",
        json={"email": "demo@example.com", "password": "Password123"},
    )
    assert register_resp.status_code == 200
    assert register_resp.json()["email"] == "demo@example.com"

    login_resp = client.post(
        "/api/v1/users/login",
        json={"email": "demo@example.com", "password": "Password123"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["token_type"] == "bearer"
    assert login_resp.json()["refresh_token"] == "fake-refresh-token"

    refresh_resp = client.post(
        "/api/v1/users/refresh-token",
        json={"refresh_token": "fake-refresh-token"},
    )
    assert refresh_resp.status_code == 200
    assert refresh_resp.json()["access_token"] == "new-access-token"
    assert refresh_resp.json()["refresh_token"] == "new-refresh-token"

    me_resp = client.get("/api/v1/users/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["user_id"] == 1


def test_auth_required_placeholder() -> None:
    """无鉴权访问受保护接口应返回 401。"""
    app = FastAPI()
    app.include_router(build_api_router())
    client = TestClient(app)

    resp = client.get("/api/v1/files")
    assert resp.status_code == 401


def test_auth_header_format_placeholder() -> None:
    """非法 Authorization 头应返回 401。"""
    app = FastAPI()
    app.include_router(build_api_router())
    client = TestClient(app)

    resp = client.get("/api/v1/files", headers={"Authorization": "Bearer invalid-token"})
    assert resp.status_code == 401


def test_refresh_token_invalid_placeholder() -> None:
    client = _build_client_for_user_routes()
    resp = client.post(
        "/api/v1/users/refresh-token",
        json={"refresh_token": "bad-refresh-token"},
    )
    assert resp.status_code == 401
