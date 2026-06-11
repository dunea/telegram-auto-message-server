# 消息历史与文件管理页面与路由（Task 7）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Telegram 消息历史记录与本地/S3 文件管理的前端页面、后端 Web 路由，并编写自动化单元测试，确保用户可以清晰地查阅群发/收发历史并管理上传的媒体/文档文件。

**Architecture:** 采用 FastAPI + Jinja2Templates 渲染服务端 HTML 页面，前端利用 Tailwind CSS 搭建精美、响应式的 UI 布局。通过 HTMX 或标准表单提交进行无缝的文件上传、下载及软删除交互。后端与 `FileService` 及数据库模型 `TelegramMessage`、`FileRecord`、`TelegramAccount` 进行无缝对接。

**Tech Stack:** Python, FastAPI, SQLAlchemy, Jinja2, Tailwind CSS, Pytest.

---

## 计划分解与执行

### Task 1: 完善并实现 `app/web/routes/messages.py` 的 Web 路由

**Files:**
- Modify: `app/web/routes/messages.py`

- [ ] **Step 1: 编写完整的 `app/web/routes/messages.py` 路由逻辑**

展示合并的群发与历史消息记录，支持 `account_id`、`direction` 过滤，查询数据库并支持分页（最新 100 条）。

```python
import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.models.account import TelegramAccount
from app.models.message import TelegramMessage
from app.web.dependencies import get_current_user_from_cookie

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates")

router = APIRouter(prefix="/web", tags=["web-messages"])


@router.get("/messages", response_class=HTMLResponse)
async def list_messages(
    request: Request,
    account_id: int | None = None,
    direction: str | None = None,
    limit: int = 100,
    offset: int = 0,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: Session = Depends(get_db_session),
):
    # 查询所有托管账号，用于在顶部下拉筛选
    accounts = db_session.scalars(
        select(TelegramAccount).order_by(TelegramAccount.id)
    ).all()
    accounts_map = {acc.id: acc for acc in accounts}

    # 构建消息查询语句
    stmt = select(TelegramMessage).order_by(TelegramMessage.id.desc())

    # 按托管账号过滤
    if account_id and account_id > 0:
        stmt = stmt.where(TelegramMessage.account_id == account_id)

    # 按消息方向过滤
    if direction:
        stmt = stmt.where(TelegramMessage.direction == direction)

    # 分页限制
    stmt = stmt.limit(limit).offset(offset)
    messages = db_session.scalars(stmt).all()

    return templates.TemplateResponse(
        "messages/list.html",
        {
            "request": request,
            "user_id": user_id,
            "messages": messages,
            "accounts": accounts,
            "accounts_map": accounts_map,
            "selected_account_id": account_id,
            "selected_direction": direction,
        },
    )
```

---

### Task 2: 完善并实现 `app/web/routes/files.py` 的 Web 路由

**Files:**
- Modify: `app/web/routes/files.py`

- [ ] **Step 1: 编写完整的 `app/web/routes/files.py` 路由逻辑**

实现文件列表查询、文件上传、删除和下载。

```python
import logging
import os
from urllib.parse import quote
from fastapi import APIRouter, Depends, Request, UploadFile, File, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_file_service
from app.models.file import FileRecord
from app.service.file_service import FileService
from app.web.dependencies import get_current_user_from_cookie

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates")

# 添加 os.path.basename 到 Jinja2 模板过滤器中，方便获取文件名
templates.env.filters["basename"] = lambda path: os.path.basename(path) if path else ""

router = APIRouter(prefix="/web", tags=["web-files"])


@router.get("/files", response_class=HTMLResponse)
async def list_files(
    request: Request,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: Session = Depends(get_db_session),
):
    # SQLAlchemy 查询 FileRecord
    stmt = select(FileRecord).order_by(FileRecord.id.desc())
    files = db_session.scalars(stmt).all()

    return templates.TemplateResponse(
        "files/list.html",
        {
            "request": request,
            "user_id": user_id,
            "files": files,
        },
    )


@router.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    content = await file.read()
    file_service.UploadFile(filename=file.filename, content=content)
    return RedirectResponse(url="/web/files", status_code=303)


@router.post("/files/{file_id}/delete")
async def delete_file(
    file_id: int,
    file_service: FileService = Depends(get_file_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    try:
        file_service.SoftDeleteFile(file_id=file_id)
    except ValueError as e:
        logger.warning(f"删除文件失败: {e}")
    return RedirectResponse(url="/web/files", status_code=303)


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int,
    file_service: FileService = Depends(get_file_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    try:
        content, filename, mime_type = file_service.DownloadFile(file_id=file_id)
        encoded_filename = quote(filename)
        return Response(
            content=content,
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}"
            },
        )
    except ValueError as e:
        logger.error(f"下载文件失败: {e}")
        return HTMLResponse(content=f"<h3>下载文件出错: {str(e)}</h3>", status_code=404)
```

---

### Task 3: 完善前端消息历史模板 `templates/messages/list.html`

**Files:**
- Create: `templates/messages/list.html`

- [ ] **Step 1: 创建 `templates/messages/list.html` 模板**

包含筛选表单和消息历史明细展示。

```html
{% extends "base.html" %}
{% block title %}群发与历史消息记录 - TG 自动消息服务{% endblock %}
{% block content %}
<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
    <!-- Header -->
    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
        <div>
            <h1 class="text-2xl font-bold text-gray-900">群发与历史消息记录</h1>
            <p class="text-sm text-gray-500 mt-1">查看所有托管账号的入站、出站及群发消息，支持多维度过滤筛选。</p>
        </div>
        <div class="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full md:w-auto">
            <!-- Account Filter -->
            <div class="flex items-center gap-2">
                <label for="account-filter" class="text-sm font-medium text-gray-700 whitespace-nowrap">筛选账号:</label>
                <select id="account-filter" onchange="filterMessages()"
                        class="block rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-1.5 border">
                    <option value="">-- 全部账号 --</option>
                    {% for acc in accounts %}
                    <option value="{{ acc.id }}" {% if selected_account_id|string == acc.id|string %}selected{% endif %}>
                        {{ acc.display_name or acc.phone_number }}
                    </option>
                    {% endfor %}
                </select>
            </div>
            <!-- Direction Filter -->
            <div class="flex items-center gap-2">
                <label for="direction-filter" class="text-sm font-medium text-gray-700 whitespace-nowrap">消息方向:</label>
                <select id="direction-filter" onchange="filterMessages()"
                        class="block rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-1.5 border">
                    <option value="">-- 全部 --</option>
                    <option value="out" {% if selected_direction == 'out' %}selected{% endif %}>出站 (Out)</option>
                    <option value="in" {% if selected_direction == 'in' %}selected{% endif %}>入站 (In)</option>
                </select>
            </div>
        </div>
    </div>

    <!-- Message List Table -->
    <div class="bg-white shadow overflow-hidden sm:rounded-lg">
        <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">发送时间</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">托管账号</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">消息方向</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">会话 Target</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">内容类型</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">消息内容</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">发送状态</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    {% if not messages %}
                    <tr>
                        <td colspan="7" class="px-6 py-10 text-center text-sm text-gray-500">
                            暂无任何消息记录。
                        </td>
                    </tr>
                    {% endif %}
                    {% for msg in messages %}
                    <tr class="hover:bg-gray-50 transition duration-150 text-sm">
                        <!-- 发送时间 -->
                        <td class="px-6 py-4 whitespace-nowrap text-gray-500 font-mono text-xs">
                            {{ msg.created_at.strftime('%Y-%m-%d %H:%M:%S') if msg.created_at else '' }}
                        </td>
                        <!-- 托管账号 -->
                        <td class="px-6 py-4 whitespace-nowrap text-gray-900 font-medium">
                            {% set acc = accounts_map.get(msg.account_id) %}
                            {% if acc %}
                                <span class="text-indigo-600">{{ acc.display_name or acc.phone_number }}</span>
                            {% else %}
                                <span class="text-gray-400">未知账号 (ID: {{ msg.account_id }})</span>
                            {% endif %}
                        </td>
                        <!-- 消息方向 -->
                        <td class="px-6 py-4 whitespace-nowrap">
                            {% if msg.direction == 'in' %}
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                入站 (In)
                            </span>
                            {% else %}
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                出站 (Out)
                            </span>
                            {% endif %}
                        </td>
                        <!-- 会话 Target -->
                        <td class="px-6 py-4 whitespace-nowrap text-gray-700 font-mono">
                            {{ msg.conversation_peer or '未知' }}
                        </td>
                        <!-- 内容类型 -->
                        <td class="px-6 py-4 whitespace-nowrap text-gray-500">
                            {{ msg.content_type }}
                        </td>
                        <!-- 消息内容 -->
                        <td class="px-6 py-4 text-gray-700 max-w-md break-all">
                            {% if msg.content_type == 'media' %}
                                <span class="text-xs text-indigo-500 font-medium bg-indigo-50 px-2 py-1 rounded">
                                    [媒体: {{ msg.media_type }}]
                                </span>
                                {% if msg.text_content %}
                                    <span class="ml-1">{{ msg.text_content }}</span>
                                {% endif %}
                                {% if msg.media_url %}
                                    <div class="mt-1 text-xs text-gray-400 font-mono truncate">
                                        URL: <a href="{{ msg.media_url }}" target="_blank" class="underline hover:text-indigo-600">{{ msg.media_url }}</a>
                                    </div>
                                {% endif %}
                            {% elif msg.content_type == 'emoji' %}
                                <span class="text-lg">{{ msg.emoji }}</span>
                            {% else %}
                                {{ msg.text_content or '' }}
                            {% endif %}
                        </td>
                        <!-- 发送状态 -->
                        <td class="px-6 py-4 whitespace-nowrap">
                            {% if msg.status == 'sent' %}
                            <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                                已发送
                            </span>
                            {% elif msg.status == 'failed' %}
                            <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800" title="{{ msg.error_message }}">
                                失败
                            </span>
                            {% else %}
                            <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
                                等待发送
                            </span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<script>
function filterMessages() {
    const acc = document.getElementById('account-filter').value;
    const dir = document.getElementById('direction-filter').value;
    
    let url = '/web/messages';
    const params = [];
    if (acc) {
        params.push('account_id=' + acc);
    }
    if (dir) {
        params.push('direction=' + dir);
    }
    if (params.length > 0) {
        url += '?' + params.join('&');
    }
    window.location.href = url;
}
</script>
{% endblock %}
```

---

### Task 4: 完善前端文件管理模板 `templates/files/list.html`

**Files:**
- Create: `templates/files/list.html`

- [ ] **Step 1: 创建 `templates/files/list.html` 模板**

包含上传表单和文件历史列表，包含过期时间、软删除按钮。

```html
{% extends "base.html" %}
{% block title %}本地与云端存储文件管理 - TG 自动消息服务{% endblock %}
{% block content %}
<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
    <!-- Header -->
    <div class="mb-6">
        <h1 class="text-2xl font-bold text-gray-900">文件存储与管理</h1>
        <p class="text-sm text-gray-500 mt-1">上传及管理用于 Telegram 发送的本地临时文件（自动异步备份至 S3 存储桶）。</p>
    </div>

    <!-- Upload Form Card -->
    <div class="bg-white shadow sm:rounded-lg mb-8 border border-gray-200">
        <div class="px-4 py-5 sm:p-6">
            <h3 class="text-lg leading-6 font-medium text-gray-900">上传新文件</h3>
            <div class="mt-2 max-w-xl text-sm text-gray-500">
                <p>支持媒体、文档或图片等多种格式，上传后系统将创建生命周期并托管到分布式文件存储中。</p>
            </div>
            <form action="/web/files/upload" method="post" enctype="multipart/form-data" class="mt-5 sm:flex sm:items-center">
                <div class="w-full sm:max-w-xs">
                    <label class="sr-only">选择文件</label>
                    <input type="file" name="file" required
                           class="block w-full border border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm px-3 py-1.5 text-gray-600 bg-white">
                </div>
                <button type="submit"
                        class="mt-3 w-full inline-flex items-center justify-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:ml-3 sm:w-auto transition">
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                    开始上传
                </button>
            </form>
        </div>
    </div>

    <!-- Files Table Card -->
    <div class="bg-white shadow overflow-hidden sm:rounded-lg border border-gray-200">
        <div class="px-4 py-5 border-b border-gray-200 sm:px-6">
            <h3 class="text-lg leading-6 font-medium text-gray-900">所有托管文件列表</h3>
        </div>
        <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">文件 ID</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">文件名 (本地路径)</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">S3 状态</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">大小 (Bytes)</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">创建时间</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">过期时间</th>
                        <th scope="col" class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    {% if not files %}
                    <tr>
                        <td colspan="7" class="px-6 py-10 text-center text-sm text-gray-500">
                            暂无任何托管文件。请在上方上传一个新文件开始。
                        </td>
                    </tr>
                    {% endif %}
                    {% for file in files %}
                    <tr class="hover:bg-gray-50 transition duration-150 text-sm">
                        <!-- 文件 ID -->
                        <td class="px-6 py-4 whitespace-nowrap font-mono text-gray-500 font-bold">
                            #{{ file.id }}
                        </td>
                        <!-- 文件名 -->
                        <td class="px-6 py-4 whitespace-nowrap text-gray-900 max-w-xs truncate" title="{{ file.local_path }}">
                            <span class="font-medium text-gray-900">{{ file.local_path | basename }}</span>
                            <div class="text-xs text-gray-400 mt-1 font-mono truncate">{{ file.local_path }}</div>
                        </td>
                        <!-- S3 状态 -->
                        <td class="px-6 py-4 whitespace-nowrap">
                            {% if file.status == 'uploaded' %}
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                Uploaded (已同步)
                            </span>
                            {% elif file.status == 'pending' %}
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                                Pending (等待同步)
                            </span>
                            {% elif file.status == 'deleted' %}
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                                Deleted (已软删除)
                            </span>
                            {% else %}
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                {{ file.status }}
                            </span>
                            {% endif %}
                        </td>
                        <!-- 文件大小 -->
                        <td class="px-6 py-4 whitespace-nowrap text-gray-500 font-mono">
                            {{ file.file_size_bytes }} B
                        </td>
                        <!-- 创建时间 -->
                        <td class="px-6 py-4 whitespace-nowrap text-gray-500 text-xs font-mono">
                            {{ file.created_at.strftime('%Y-%m-%d %H:%M:%S') if file.created_at else '' }}
                        </td>
                        <!-- 过期时间 -->
                        <td class="px-6 py-4 whitespace-nowrap text-gray-500 text-xs font-mono">
                            {{ file.expires_at.strftime('%Y-%m-%d %H:%M:%S') if file.expires_at else '无' }}
                        </td>
                        <!-- 操作 -->
                        <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                            <div class="flex items-center justify-end gap-3">
                                {% if file.status != 'deleted' %}
                                <a href="/web/files/{{ file.id }}/download" 
                                   class="text-indigo-600 hover:text-indigo-900 flex items-center bg-indigo-50 hover:bg-indigo-100 px-2.5 py-1 rounded transition">
                                    下载
                                </a>
                                <form action="/web/files/{{ file.id }}/delete" method="post" onsubmit="return confirm('确定要软删除并清理该文件吗？');">
                                    <button type="submit" 
                                            class="text-red-600 hover:text-red-900 flex items-center bg-red-50 hover:bg-red-100 px-2.5 py-1 rounded transition">
                                        软删除
                                    </button>
                                </form>
                                {% else %}
                                <span class="text-gray-400 italic text-xs">无可用操作</span>
                                {% endif %}
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
{% endblock %}
```

---

### Task 5: 编写单元测试并验证集成

**Files:**
- Create: `tests/test_web_messages_files.py`

- [ ] **Step 1: 创建单元测试文件**

包含完整的鉴权 mock、消息查询和过滤、文件上传、下载、删除测试，覆盖 100% 流程。

```python
import io
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.account import TelegramAccount
from app.models.file import FileRecord
from app.models.message import TelegramMessage
from app.web.dependencies import get_current_user_from_cookie


@pytest.fixture
def override_auth():
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    yield
    app.dependency_overrides.pop(get_current_user_from_cookie, None)


def test_list_messages_web(db_session, override_auth):
    client = TestClient(app)

    # 1. 制造测试账号
    acc = TelegramAccount(
        phone_number="+8618888888888",
        display_name="测试账号",
        is_online=True,
        is_active=True,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)

    # 2. 制造测试消息
    msg1 = TelegramMessage(
        account_id=acc.id,
        direction="out",
        conversation_peer="user_123",
        content_type="text",
        text_content="Hello out",
        status="sent",
        created_at=datetime.utcnow(),
    )
    msg2 = TelegramMessage(
        account_id=acc.id,
        direction="in",
        conversation_peer="user_123",
        content_type="text",
        text_content="Hello in",
        status="sent",
        created_at=datetime.utcnow(),
    )
    db_session.add_all([msg1, msg2])
    db_session.commit()

    # 3. 访问列表页
    resp = client.get("/web/messages")
    assert resp.status_code == 200
    assert "Hello out" in resp.text
    assert "Hello in" in resp.text

    # 4. 按 account 筛选
    resp = client.get(f"/web/messages?account_id={acc.id}")
    assert resp.status_code == 200
    assert "测试账号" in resp.text

    # 5. 按 direction 筛选
    resp = client.get("/web/messages?direction=out")
    assert resp.status_code == 200
    assert "Hello out" in resp.text
    assert "Hello in" not in resp.text


def test_files_web_flow(db_session, override_auth, tmp_path):
    client = TestClient(app)

    # 1. 测试文件上传
    file_content = b"fake-file-bytes"
    file_data = {"file": ("test_upload_file.txt", io.BytesIO(file_content), "text/plain")}

    resp = client.post("/web/files/upload", files=file_data, follow_redirects=False)
    # 应 303 重定向到 /web/files
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/files"

    # 2. 查询上传记录
    record = db_session.scalars(select(FileRecord).order_by(FileRecord.id.desc())).first()
    assert record is not None
    assert "test_upload_file.txt" in record.local_path

    # 3. 访问列表页
    resp_list = client.get("/web/files")
    assert resp_list.status_code == 200
    assert "test_upload_file.txt" in resp_list.text

    # 4. 测试下载路由
    resp_dl = client.get(f"/web/files/{record.id}/download")
    assert resp_dl.status_code == 200
    assert resp_dl.content == file_content
    assert "test_upload_file.txt" in resp_dl.headers["Content-Disposition"]

    # 5. 测试删除路由
    resp_del = client.post(f"/web/files/{record.id}/delete", follow_redirects=False)
    assert resp_del.status_code == 303
    assert resp_del.headers["location"] == "/web/files"

    # 验证是否已被软删除
    db_session.refresh(record)
    assert record.status == "deleted"
```

- [ ] **Step 2: 运行测试并确保 100% 通过**

运行：`pytest tests/test_web_messages_files.py -v`
确保所有测试都通过（PASS）。

---

## 计划自评与执行选择

- **Spec coverage:** 覆盖消息列表多维度筛选（account_id 和 direction）展示，文件管理页面（上传、下载、软删除、状态、生命周期展现等）。
- **Placeholder scan:** 无任何 Placeholder、TODO，直接提供了完整的全量代码和模板内容。
- **Type consistency:** 路由内 SQLAlchemy 的语法完全符合 FastAPI 项目已有约束和 Mapped 定义。

请开始执行！
