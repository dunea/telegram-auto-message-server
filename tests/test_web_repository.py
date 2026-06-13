"""项目仓库页面与路由单元测试。"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web.routes.repository import router as repository_router, _cached_data
from app.web import register_web_routes

# 模拟 GitHub API 返回的仓库元数据
MOCK_REPO_JSON = {
    "name": "telegram-auto-message-server",
    "full_name": "dunea/telegram-auto-message-server",
    "description": "Telegram 自动消息服务端（FastAPI + Telethon + MySQL + APScheduler）",
    "html_url": "https://github.com/dunea/telegram-auto-message-server",
    "stargazers_count": 42,
    "forks_count": 8,
    "open_issues_count": 1,
    "license": {"name": "MIT License"},
    "pushed_at": "2026-06-14T03:22:22Z"
}

# 模拟 GitHub API 返回的 Commits 列表
MOCK_COMMITS_JSON = [
    {
        "sha": "abcdef1234567890abcdef1234567890abcdef12",
        "commit": {
            "message": "feat: 增加公开仓库描述和 Commits 显示页面",
            "author": {
                "name": "dunea",
                "email": "dunea@example.com",
                "date": "2026-06-14T03:20:00Z"
            }
        },
        "author": {
            "avatar_url": "https://avatars.githubusercontent.com/u/12345",
            "html_url": "https://github.com/dunea"
        }
    }
]

class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code
        self.text = str(json_data)
        
    def json(self):
        return self._json_data


@pytest.fixture(autouse=True)
def clean_cache():
    """每次测试前清理全局缓存"""
    global _cached_data
    _cached_data["repo_info"] = None
    _cached_data["commits"] = None
    _cached_data["updated_at"] = None


@patch("httpx.AsyncClient")
def test_repository_page_success(mock_client_class) -> None:
    """测试 GitHub API 正常响应时成功渲染页面。"""
    app = FastAPI()
    register_web_routes(app)
    
    mock_client = AsyncMock()
    mock_client_class.return_value = mock_client
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_get(url, *args, **kwargs):
        if "commits" in str(url):
            return MockResponse(MOCK_COMMITS_JSON, 200)
        return MockResponse(MOCK_REPO_JSON, 200)
        
    mock_client.get.side_effect = mock_get

    client = TestClient(app)
    resp = client.get("/web/repository")
        
    assert resp.status_code == 200
    assert "dunea/telegram-auto-message-server" in resp.text
    assert "feat: 增加公开仓库描述和 Commits 显示页面" in resp.text
    assert "dunea" in resp.text
    assert "abcdef1" in resp.text  # 短 SHA


@patch("httpx.AsyncClient")
def test_repository_page_api_error_no_cache(mock_client_class) -> None:
    """测试 GitHub API 报错且无缓存时，优雅地渲染错误页面。"""
    app = FastAPI()
    register_web_routes(app)

    mock_client = AsyncMock()
    mock_client_class.return_value = mock_client
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    
    mock_client.get.side_effect = Exception("Connection Timeout")

    client = TestClient(app)
    resp = client.get("/web/repository")
        
    assert resp.status_code == 200
    assert "获取仓库信息失败" in resp.text
    assert "暂时无法获取仓库数据，请稍后重试。" in resp.text


@patch("httpx.AsyncClient")
def test_repository_page_api_error_with_cache_fallback(mock_client_class) -> None:
    """测试 GitHub API 报错时，若有历史缓存则使用缓存数据进行兜底。"""
    app = FastAPI()
    register_web_routes(app)
    
    # 手动填充一些历史缓存数据
    global _cached_data
    _cached_data["repo_info"] = {
        "name": "telegram-auto-message-server",
        "full_name": "dunea/telegram-auto-message-server",
        "description": "Cached Description",
        "html_url": "https://github.com/dunea/telegram-auto-message-server",
        "stargazers_count": 10,
        "forks_count": 2,
        "license": "MIT",
        "pushed_at": "2026-06-14 00:00:00",
    }
    _cached_data["commits"] = [
        {
            "sha": "9999999999999999999999999999999999999999",
            "short_sha": "9999999",
            "message": "Cached Commit Message",
            "author_name": "Cached Author",
            "date": "2026-06-14 01:00:00",
            "avatar_url": None,
            "html_url": "#",
        }
    ]
    import time
    _cached_data["updated_at"] = time.time() - 400  # 让缓存失效，以便触发 fetch_github_data() 内部请求

    mock_client = AsyncMock()
    mock_client_class.return_value = mock_client
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    
    mock_client.get.side_effect = Exception("GitHub API Down")

    client = TestClient(app)
    resp = client.get("/web/repository")
        
    assert resp.status_code == 200
    # 页面中应该能正常展示历史缓存中的内容
    assert "Cached Description" in resp.text
    assert "Cached Commit Message" in resp.text
    assert "Cached Author" in resp.text
    # 并且不应该有缓存兜底的警告提示或手动刷新字样
    assert "接口请求超频" not in resp.text
    assert "手动刷新" not in resp.text
