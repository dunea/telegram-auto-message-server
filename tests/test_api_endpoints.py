"""新增 API 端点的轻量级冒烟测试。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import (
    get_auto_reply_service,
    get_current_user,
    get_file_service,
    get_task_service,
    get_telegram_service,
)
from app.api.router import build_api_router


class FakeTelegramService:
    async def RequestPhoneLoginCode(self, phone_number: str, proxy_id: int | None = None) -> dict:
        if phone_number == "+00000000000":
            raise ValueError("手机号无效")
        return {
            "account_id": 1,
            "phone_number": phone_number,
            "is_active": True,
            "is_online": False,
            "next_step": "verify_code",
            "message": "验证码已发送，请提交验证码。",
            "phone_code_hash": "hash-001",
        }

    async def CreateAccountWithSessionLogin(self, phone_number: str, session_string: str, proxy_id: int | None = None) -> dict:
        return {
            "account_id": 2,
            "phone_number": phone_number,
            "is_active": True,
            "is_online": True,
            "next_step": "done",
            "message": "账号通过 session 登录成功。",
        }

    def SetAccountActive(self, account_id: int, is_active: bool) -> dict:
        if account_id == 404:
            raise ValueError("账号不存在")
        return {
            "account_id": account_id,
            "phone_number": "+8613800000000",
            "is_active": is_active,
            "is_online": False,
        }

    def SoftDeleteAccount(self, account_id: int) -> dict:
        if account_id == 404:
            raise ValueError("账号不存在")
        return {"account_id": account_id, "deleted": True}


class FakeTaskService:
    def __init__(self) -> None:
        self._task = {
            "task_id": 10,
            "account_id": 1,
            "cron_expr": "0 9 * * *",
            "target_identifier": "@target",
            "message_template": "hello",
            "message_content_id": None,
            "is_active": True,
        }

    def ListScheduledTasksByAccountId(self, account_id: int, limit: int, offset: int) -> dict:
        _ = (limit, offset)
        return {"total": 1, "items": [{**self._task, "account_id": account_id}]}

    def SetScheduledTaskActive(self, task_id: int, is_active: bool) -> dict:
        if task_id == 404:
            raise ValueError("定时消息不存在")
        self._task["task_id"] = task_id
        self._task["is_active"] = is_active
        return dict(self._task)


class FakeAutoReplyService:
    def __init__(self) -> None:
        self._rule = {
            "rule_id": 1,
            "account_id": 1,
            "trigger_keyword": "hi",
            "reply_content": "hello",
            "is_active": True,
        }

    def CreateRule(self, account_id: int, trigger_keyword: str, reply_content: str) -> dict:
        self._rule = {
            "rule_id": 2,
            "account_id": account_id,
            "trigger_keyword": trigger_keyword,
            "reply_content": reply_content,
            "is_active": True,
        }
        return dict(self._rule)

    def ListRulesByAccountId(self, account_id: int, limit: int, offset: int) -> dict:
        _ = (limit, offset)
        return {"total": 1, "items": [{**self._rule, "account_id": account_id}]}

    def GetRuleById(self, rule_id: int) -> dict:
        if rule_id == 404:
            raise ValueError("回复消息不存在")
        return {**self._rule, "rule_id": rule_id}

    def UpdateRule(self, rule_id: int, trigger_keyword: str, reply_content: str) -> dict:
        if rule_id == 404:
            raise ValueError("回复消息不存在")
        self._rule = {
            "rule_id": rule_id,
            "account_id": self._rule["account_id"],
            "trigger_keyword": trigger_keyword,
            "reply_content": reply_content,
            "is_active": self._rule["is_active"],
        }
        return dict(self._rule)

    def SetRuleActive(self, rule_id: int, is_active: bool) -> dict:
        if rule_id == 404:
            raise ValueError("回复消息不存在")
        self._rule["rule_id"] = rule_id
        self._rule["is_active"] = is_active
        return dict(self._rule)

    def SoftDeleteRule(self, rule_id: int) -> dict:
        if rule_id == 404:
            raise ValueError("回复消息不存在")
        return {"rule_id": rule_id, "deleted": True}


class FakeFileService:
    def __init__(self) -> None:
        self._file = {
            "file_id": 11,
            "filename": "hello.txt",
            "status": "uploaded",
            "size_bytes": 5,
            "s3_key": "uploads/hello.txt",
            "s3_url": "https://example.com/uploads/hello.txt",
            "created_at": None,
            "expires_at": None,
        }

    def UploadFile(self, filename: str, content: bytes) -> dict:
        if len(content) == 0:
            raise ValueError("文件内容不能为空")
        self._file["filename"] = filename
        self._file["size_bytes"] = len(content)
        return {
            "file_id": self._file["file_id"],
            "filename": self._file["filename"],
            "status": self._file["status"],
            "size_bytes": self._file["size_bytes"],
            "s3_key": self._file["s3_key"],
            "s3_url": self._file["s3_url"],
        }

    def ListFiles(self, status: str | None, limit: int, offset: int) -> dict:
        _ = (status, limit, offset)
        return {"total": 1, "items": [dict(self._file)]}

    def GetFileById(self, file_id: int) -> dict:
        if file_id == 404:
            raise ValueError("文件不存在")
        return {**self._file, "file_id": file_id}

    def DownloadFile(self, file_id: int) -> tuple[bytes, str, str]:
        if file_id == 404:
            raise ValueError("文件不存在")
        _ = file_id
        return b"hello", self._file["filename"], "text/plain"

    def SoftDeleteFile(self, file_id: int) -> dict:
        if file_id == 404:
            raise ValueError("文件不存在")
        return {"file_id": file_id, "deleted": True}


def _build_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(build_api_router())
    app.dependency_overrides[get_telegram_service] = lambda: FakeTelegramService()
    app.dependency_overrides[get_task_service] = lambda: FakeTaskService()
    app.dependency_overrides[get_auto_reply_service] = lambda: FakeAutoReplyService()
    app.dependency_overrides[get_file_service] = lambda: FakeFileService()
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}
    return TestClient(app)


def test_accounts_login_and_status_and_delete() -> None:
    client = _build_test_client()

    request_code_resp = client.post(
        "/api/v1/accounts/login/phone/request-code",
        json={"phone_number": "+8613800000001", "proxy_id": None},
    )
    assert request_code_resp.status_code == 200
    assert request_code_resp.json()["next_step"] == "verify_code"

    session_login_resp = client.post(
        "/api/v1/accounts/login/session",
        json={"phone_number": "+8613800000002", "session_string": "abc123session-token", "proxy_id": None},
    )
    assert session_login_resp.status_code == 200
    assert session_login_resp.json()["next_step"] == "done"

    active_resp = client.patch("/api/v1/accounts/2/active", json={"is_active": False})
    assert active_resp.status_code == 200
    assert active_resp.json()["is_active"] is False

    delete_resp = client.delete("/api/v1/accounts/2")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True


def test_accounts_failure_paths() -> None:
    client = _build_test_client()

    request_code_resp = client.post(
        "/api/v1/accounts/login/phone/request-code",
        json={"phone_number": "+00000000000", "proxy_id": None},
    )
    assert request_code_resp.status_code == 400

    active_resp = client.patch("/api/v1/accounts/404/active", json={"is_active": True})
    assert active_resp.status_code == 404

    delete_resp = client.delete("/api/v1/accounts/404")
    assert delete_resp.status_code == 404


def test_scheduled_task_list_and_active() -> None:
    client = _build_test_client()

    list_resp = client.get("/api/v1/tasks/schedule", params={"account_id": 1, "limit": 20, "offset": 0})
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    active_resp = client.patch("/api/v1/tasks/schedule/10/active", json={"is_active": False})
    assert active_resp.status_code == 200
    assert active_resp.json()["is_active"] is False


def test_scheduled_task_active_not_found() -> None:
    client = _build_test_client()
    active_resp = client.patch("/api/v1/tasks/schedule/404/active", json={"is_active": False})
    assert active_resp.status_code == 404


def test_auto_reply_rule_crud() -> None:
    client = _build_test_client()

    create_resp = client.post(
        "/api/v1/auto-reply-rules",
        json={"account_id": 1, "trigger_keyword": "ping", "reply_content": "pong"},
    )
    assert create_resp.status_code == 200
    assert create_resp.json()["trigger_keyword"] == "ping"

    list_resp = client.get("/api/v1/auto-reply-rules", params={"account_id": 1, "limit": 20, "offset": 0})
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    update_resp = client.put(
        "/api/v1/auto-reply-rules/2",
        json={"trigger_keyword": "hello", "reply_content": "world"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["reply_content"] == "world"

    disable_resp = client.patch("/api/v1/auto-reply-rules/2/active", json={"is_active": False})
    assert disable_resp.status_code == 200
    assert disable_resp.json()["is_active"] is False

    delete_resp = client.delete("/api/v1/auto-reply-rules/2")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True


def test_auto_reply_rule_not_found_paths() -> None:
    client = _build_test_client()

    get_resp = client.get("/api/v1/auto-reply-rules/404")
    assert get_resp.status_code == 404

    update_resp = client.put(
        "/api/v1/auto-reply-rules/404",
        json={"trigger_keyword": "hello", "reply_content": "world"},
    )
    assert update_resp.status_code == 404

    disable_resp = client.patch("/api/v1/auto-reply-rules/404/active", json={"is_active": False})
    assert disable_resp.status_code == 404

    delete_resp = client.delete("/api/v1/auto-reply-rules/404")
    assert delete_resp.status_code == 404


def test_files_upload_list_download_delete() -> None:
    client = _build_test_client()

    upload_resp = client.post(
        "/api/v1/files/upload",
        files={"file": ("hello.txt", b"hello", "text/plain")},
    )
    assert upload_resp.status_code == 200
    assert upload_resp.json()["filename"] == "hello.txt"

    list_resp = client.get("/api/v1/files", params={"limit": 20, "offset": 0})
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    download_resp = client.get("/api/v1/files/11/download")
    assert download_resp.status_code == 200
    assert download_resp.content == b"hello"

    delete_resp = client.delete("/api/v1/files/11")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True


def test_files_failure_paths() -> None:
    client = _build_test_client()

    upload_resp = client.post(
        "/api/v1/files/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert upload_resp.status_code == 400

    item_resp = client.get("/api/v1/files/404")
    assert item_resp.status_code == 404

    download_resp = client.get("/api/v1/files/404/download")
    assert download_resp.status_code == 404

    delete_resp = client.delete("/api/v1/files/404")
    assert delete_resp.status_code == 404
