"""全局异常处理器测试。"""

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.startup import register_global_exception_handlers


def _build_client() -> TestClient:
    app = FastAPI()

    @app.get("/value-error")
    def value_error_route() -> None:
        raise ValueError("参数错误")

    @app.get("/permission-error")
    def permission_error_route() -> None:
        raise PermissionError("无权限访问")

    @app.get("/runtime-error")
    def runtime_error_route() -> None:
        raise RuntimeError("boom")

    @app.get("/http-error")
    def http_error_route() -> None:
        raise HTTPException(status_code=418, detail="teapot")

    register_global_exception_handlers(app)
    return TestClient(app, raise_server_exceptions=False)


def test_value_error_returns_400() -> None:
    client = _build_client()
    resp = client.get("/value-error")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "参数错误"


def test_permission_error_returns_403() -> None:
    client = _build_client()
    resp = client.get("/permission-error")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权限访问"


def test_runtime_error_returns_500() -> None:
    client = _build_client()
    resp = client.get("/runtime-error")
    assert resp.status_code == 500
    assert resp.json()["detail"] == "服务器内部错误"


def test_http_exception_keeps_default_behavior() -> None:
    client = _build_client()
    resp = client.get("/http-error")
    assert resp.status_code == 418
    assert resp.json()["detail"] == "teapot"
