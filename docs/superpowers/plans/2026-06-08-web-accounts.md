# Telegram Accounts Management Page and Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the account list page, detail page, complete HTMX multi-step login flows (request code, verify code, verify 2FA password, and session import), account soft deletion/toggle routes, and full unit tests for these behaviors.

**Architecture:** A set of FastAPI routes under `app/web/routes/accounts.py` using Jinja2 templates (`templates/accounts/*.html`) and leveraging HTMX for asynchronous interactions (re-rendering form parts on transitions, toggling active states, handling redirects). It interacts with SQLite through SQLAlchemy session and uses `TelegramService` for Telegram action adapters.

**Tech Stack:** FastAPI, Jinja2, HTMX, Tailwind CSS, SQLAlchemy, Pytest.

---

### Task 1: Create the Web Templates for Account Management

**Files:**
- Create: `templates/accounts/list.html`
- Create: `templates/accounts/detail.html`
- Create: `templates/accounts/login_flow.html`

- [ ] **Step 1: Create Account List Template (`templates/accounts/list.html`)**

Provide a robust list template that extends `base.html`. Displays telephone number, name, online status, active/disabled status, inline toggles for is_active, detail links, and a delete button. Includes an "Add Account" button linking to `/web/accounts/new`.

```html
{% extends "base.html" %}
{% block title %}账号管理 - TG 自动消息服务{% endblock %}
{% block content %}
<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
    <div class="flex justify-between items-center mb-6">
        <h1 class="text-2xl font-bold text-gray-900">账号管理</h1>
        <a href="/web/accounts/new" class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700">
            导入/登录账号
        </a>
    </div>

    <div class="bg-white shadow overflow-hidden sm:rounded-md">
        <ul role="list" class="divide-y divide-gray-200">
            {% for account in accounts %}
            <li class="p-6 hover:bg-gray-50 transition duration-150">
                <div class="flex items-center justify-between">
                    <div class="flex items-center min-w-0">
                        <div class="ml-4">
                            <p class="text-lg font-medium text-indigo-600 truncate">
                                <a href="/web/accounts/{{ account.id }}" class="hover:underline">
                                    {{ account.phone_number }}
                                </a>
                            </p>
                            <p class="text-sm text-gray-500 mt-1">
                                名称: {{ account.display_name or "未登录" }} 
                                | ID: {{ account.telegram_user_id or "-" }}
                                | 代理: {% if account.proxy_id and proxies.get(account.proxy_id) %}{{ proxies.get(account.proxy_id).proxy_host }}:{{ proxies.get(account.proxy_id).proxy_port }}{% else %}无{% endif %}
                            </p>
                        </div>
                    </div>
                    <div class="flex items-center space-x-4">
                        <!-- Online/Offline Badge -->
                        <div>
                            {% if account.is_online %}
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                在线
                            </span>
                            {% else %}
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                离线
                            </span>
                            {% endif %}
                        </div>

                        <!-- Active Toggle with HTMX -->
                        <div id="status-badge-{{ account.id }}">
                            <button hx-post="/web/accounts/{{ account.id }}/toggle-active"
                                    hx-target="#status-badge-{{ account.id }}"
                                    hx-swap="outerHTML"
                                    class="inline-flex items-center px-3 py-1.5 border border-gray-300 shadow-sm text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50">
                                {% if account.is_active %}
                                <span class="text-green-600 font-bold">● 启用中</span>
                                {% else %}
                                <span class="text-red-500 font-bold">○ 已禁用</span>
                                {% endif %}
                            </button>
                        </div>

                        <!-- Actions -->
                        <div class="flex space-x-2">
                            <a href="/web/accounts/{{ account.id }}" class="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded text-indigo-700 bg-indigo-100 hover:bg-indigo-200">
                                详情
                            </a>
                            <button hx-post="/web/accounts/{{ account.id }}/delete"
                                    hx-confirm="确认软删除此账号并停用吗？"
                                    class="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded text-red-700 bg-red-100 hover:bg-red-200">
                                删除
                            </button>
                        </div>
                    </div>
                </div>
            </li>
            {% else %}
            <li class="p-6 text-center text-gray-500">
                暂无托管账号，请点击右上角按钮导入。
            </li>
            {% endfor %}
        </ul>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Create Account Detail Template (`templates/accounts/detail.html`)**

Displays account properties and list of dialogs/conversations if the account is online. Provides inline triggers for online synchronization and toggling.

```html
{% extends "base.html" %}
{% block title %}账号详情 - TG 自动消息服务{% endblock %}
{% block content %}
<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
    <div class="mb-6 flex justify-between items-center">
        <a href="/web/accounts" class="text-indigo-600 hover:text-indigo-900 font-medium flex items-center gap-1">
            &larr; 返回账号列表
        </a>
        <div class="flex gap-2">
            <button hx-post="/web/accounts/{{ account.id }}/online"
                    class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700">
                一键上线 / 刷新
            </button>
            <button hx-post="/web/accounts/{{ account.id }}/delete"
                    hx-confirm="确认软删除该账号吗？"
                    class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700">
                停用并删除
            </button>
        </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Account Info Card -->
        <div class="bg-white shadow overflow-hidden sm:rounded-lg lg:col-span-1">
            <div class="px-4 py-5 sm:px-6">
                <h3 class="text-lg leading-6 font-medium text-gray-900">账号基本信息</h3>
                <p class="mt-1 max-w-2xl text-sm text-gray-500">托管详情及连接配置。</p>
            </div>
            <div class="border-t border-gray-200 px-4 py-5 sm:p-0">
                <dl class="sm:divide-y divide-gray-200">
                    <div class="py-3 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                        <dt class="text-sm font-medium text-gray-500">手机号</dt>
                        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">{{ account.phone_number }}</dd>
                    </div>
                    <div class="py-3 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                        <dt class="text-sm font-medium text-gray-500">展示名称</dt>
                        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">{{ account.display_name or "未知" }}</dd>
                    </div>
                    <div class="py-3 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                        <dt class="text-sm font-medium text-gray-500">Telegram ID</dt>
                        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">{{ account.telegram_user_id or "未获取" }}</dd>
                    </div>
                    <div class="py-3 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                        <dt class="text-sm font-medium text-gray-500">在线状态</dt>
                        <dd class="mt-1 text-sm sm:mt-0 sm:col-span-2">
                            {% if account.is_online %}
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">在线</span>
                            {% else %}
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">离线</span>
                            {% endif %}
                        </dd>
                    </div>
                    <div class="py-3 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                        <dt class="text-sm font-medium text-gray-500">调度启用</dt>
                        <dd class="mt-1 text-sm sm:mt-0 sm:col-span-2">
                            {% if account.is_active %}
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">已启用</span>
                            {% else %}
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">已停用</span>
                            {% endif %}
                        </dd>
                    </div>
                    <div class="py-3 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                        <dt class="text-sm font-medium text-gray-500">绑定的代理</dt>
                        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                            {% if proxy %}
                            {{ proxy.proxy_host }}:{{ proxy.proxy_port }} ({{ "SOCKS5" }})
                            {% else %}
                            无代理直连
                            {% endif %}
                        </dd>
                    </div>
                </dl>
            </div>
        </div>

        <!-- Dialogs/Conversations List -->
        <div class="bg-white shadow overflow-hidden sm:rounded-lg lg:col-span-2">
            <div class="px-4 py-5 sm:px-6 flex justify-between items-center">
                <div>
                    <h3 class="text-lg leading-6 font-medium text-gray-900">最近聊天会话</h3>
                    <p class="mt-1 max-w-2xl text-sm text-gray-500">仅在账号在线时加载最近的对话列表。</p>
                </div>
            </div>
            <div class="border-t border-gray-200">
                {% if error_msg %}
                <div class="p-4 bg-red-50 text-red-700 text-sm">
                    {{ error_msg }}
                </div>
                {% endif %}

                {% if account.is_online %}
                <ul role="list" class="divide-y divide-gray-200 max-h-[500px] overflow-y-auto">
                    {% for conv in conversations %}
                    <li class="p-4 flex justify-between items-center hover:bg-gray-50">
                        <div class="min-w-0 flex-1">
                            <p class="text-sm font-semibold text-gray-900 truncate">{{ conv.title or "群组/联系人" }}</p>
                            <p class="text-xs text-gray-500 mt-1">ID: {{ conv.id }} | 类型: {{ conv.type }}</p>
                        </div>
                        <div class="text-xs text-gray-400">
                            {% if conv.unread_count %}
                            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                                {{ conv.unread_count }}
                            </span>
                            {% endif %}
                        </div>
                    </li>
                    {% else %}
                    <li class="p-8 text-center text-gray-500">
                        没有拉取到任何活跃会话。
                    </li>
                    {% endfor %}
                </ul>
                {% else %}
                <div class="p-8 text-center text-gray-500">
                    账号当前离线，无法获取会话列表。请点击上方【一键上线】按钮。
                </div>
                {% endif %}
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Create Login Flow Template (`templates/accounts/login_flow.html`)**

Uses Tailwind Tabs to switch between **Phone OTP** login and **Session string** import. Utilizes HTMX `hx-post` and `hx-target` to handle login sequences smoothly without full-page reloads.

```html
{% extends "base.html" %}
{% block title %}添加账号 - TG 自动消息服务{% endblock %}
{% block content %}
<div class="max-w-2xl mx-auto px-4 py-8">
    <div class="mb-6">
        <a href="/web/accounts" class="text-indigo-600 hover:text-indigo-900 font-medium flex items-center gap-1">
            &larr; 返回账号列表
        </a>
    </div>

    <div class="bg-white shadow sm:rounded-lg overflow-hidden">
        <div class="border-b border-gray-200">
            <nav class="flex -mb-px" aria-label="Tabs">
                <button onclick="switchTab('phone-tab', 'session-tab')" id="phone-btn" class="w-1/2 py-4 px-1 text-center border-b-2 font-medium text-sm border-indigo-500 text-indigo-600">
                    手机验证码登录
                </button>
                <button onclick="switchTab('session-tab', 'phone-tab')" id="session-btn" class="w-1/2 py-4 px-1 text-center border-b-2 font-medium text-sm border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300">
                    直接导入 Session 字符串
                </button>
            </nav>
        </div>

        <div class="p-6">
            <!-- Tab 1: Phone Login -->
            <div id="phone-tab">
                <div id="login-flow-container">
                    <!-- Step 1 Form -->
                    <form hx-post="/web/accounts/login/phone/request-code" hx-target="#login-flow-container" hx-swap="innerHTML" class="space-y-6">
                        <div>
                            <label for="phone_number" class="block text-sm font-medium text-gray-700">手机号 (格式: +8613800000000)</label>
                            <input type="text" name="phone_number" id="phone_number" placeholder="+8613800000000" required
                                   class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                        </div>

                        <div>
                            <label for="proxy_id" class="block text-sm font-medium text-gray-700">网络代理 (可选)</label>
                            <select name="proxy_id" id="proxy_id"
                                    class="mt-1 block w-full bg-white border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                                <option value="">直连 (不使用代理)</option>
                                {% for proxy in proxies %}
                                <option value="{{ proxy.id }}">{{ proxy.proxy_host }}:{{ proxy.proxy_port }}</option>
                                {% endfor %}
                            </select>
                        </div>

                        <div>
                            <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
                                发送验证码
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Tab 2: Session Login -->
            <div id="session-tab" class="hidden">
                <div id="session-flow-container">
                    <form hx-post="/web/accounts/login/session" hx-target="#session-flow-container" hx-swap="innerHTML" class="space-y-6">
                        <div>
                            <label for="phone_number_session" class="block text-sm font-medium text-gray-700">手机号</label>
                            <input type="text" name="phone_number" id="phone_number_session" placeholder="+8613800000000" required
                                   class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                        </div>

                        <div>
                            <label for="session_string" class="block text-sm font-medium text-gray-700">Session 字符串</label>
                            <textarea name="session_string" id="session_string" rows="5" placeholder="1BJWV1tQBu..." required
                                      class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"></textarea>
                        </div>

                        <div>
                            <label for="proxy_id_session" class="block text-sm font-medium text-gray-700">网络代理 (可选)</label>
                            <select name="proxy_id" id="proxy_id_session"
                                    class="mt-1 block w-full bg-white border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                                <option value="">直连 (不使用代理)</option>
                                {% for proxy in proxies %}
                                <option value="{{ proxy.id }}">{{ proxy.proxy_host }}:{{ proxy.proxy_port }}</option>
                                {% endfor %}
                            </select>
                        </div>

                        <div>
                            <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
                                确认导入并上线
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
    function switchTab(showId, hideId) {
        document.getElementById(showId).classList.remove('hidden');
        document.getElementById(hideId).classList.add('hidden');
        
        if (showId === 'phone-tab') {
            document.getElementById('phone-btn').className = 'w-1/2 py-4 px-1 text-center border-b-2 font-medium text-sm border-indigo-500 text-indigo-600';
            document.getElementById('session-btn').className = 'w-1/2 py-4 px-1 text-center border-b-2 font-medium text-sm border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300';
        } else {
            document.getElementById('session-btn').className = 'w-1/2 py-4 px-1 text-center border-b-2 font-medium text-sm border-indigo-500 text-indigo-600';
            document.getElementById('phone-btn').className = 'w-1/2 py-4 px-1 text-center border-b-2 font-medium text-sm border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300';
        }
    }
</script>
{% endblock %}
```

---

### Task 2: Implement FastAPI Web Accounts Router

**Files:**
- Modify: `app/web/routes/accounts.py`

- [ ] **Step 1: Write routing implementation**

We will write the detailed web router in `app/web/routes/accounts.py`. We will implement:
- `GET /web/accounts`: Page with active account list.
- `GET /web/accounts/new`: Page containing login tabs.
- `POST /web/accounts/login/phone/request-code`: Submits phone request and returns code verification HTML fragment.
- `POST /web/accounts/{account_id}/login/phone/verify-code`: Verifies code and either returns 2FA password HTML fragment or sets `HX-Redirect` header to finish.
- `POST /web/accounts/{account_id}/login/phone/verify-password`: Submits 2FA and sets `HX-Redirect` header.
- `POST /web/accounts/login/session`: Direct session string import.
- `GET /web/accounts/{account_id}`: Account details with recent conversations if online.
- `POST /web/accounts/{account_id}/toggle-active`: Toggle account active and return the status button segment.
- `POST /web/accounts/{account_id}/delete`: Soft delete account and redirect.
- `POST /web/accounts/{account_id}/online`: Put account online and trigger state refresh.

```python
import logging
from typing import Any
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_telegram_service
from app.models.account import TelegramAccount, ProxyInfo
from app.service.telegram_service import TelegramService
from app.web.dependencies import get_current_user_from_cookie

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates")

router = APIRouter(prefix="/web", tags=["web-accounts"])

@router.get("/accounts", response_class=HTMLResponse)
async def list_accounts(
    request: Request,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: Session = Depends(get_db_session)
):
    accounts = db_session.scalars(select(TelegramAccount).order_by(TelegramAccount.id)).all()
    proxies = {p.id: p for p in db_session.scalars(select(ProxyInfo)).all()}
    return templates.TemplateResponse("accounts/list.html", {
        "request": request,
        "user_id": user_id,
        "accounts": accounts,
        "proxies": proxies
    })

@router.get("/accounts/new", response_class=HTMLResponse)
async def new_account_page(
    request: Request,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: Session = Depends(get_db_session)
):
    proxies = db_session.scalars(select(ProxyInfo).where(ProxyInfo.is_active == True)).all()
    return templates.TemplateResponse("accounts/login_flow.html", {
        "request": request,
        "user_id": user_id,
        "proxies": proxies
    })

@router.post("/accounts/login/phone/request-code")
async def request_phone_code(
    phone_number: str = Form(...),
    proxy_id: str = Form(""),
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    pid = int(proxy_id) if proxy_id and proxy_id.strip() else None
    try:
        res = await telegram_service.RequestPhoneLoginCode(phone_number, proxy_id=pid)
        account_id = res["account_id"]
        phone_code_hash = res["phone_code_hash"]
        return HTMLResponse(f"""
            <form hx-post="/web/accounts/{account_id}/login/phone/verify-code" hx-target="#login-flow-container" hx-swap="innerHTML" class="space-y-6">
                <input type="hidden" name="phone_code_hash" value="{phone_code_hash}">
                <div class="bg-blue-50 border-l-4 border-blue-400 p-4 mb-4">
                    <p class="text-sm text-blue-700">验证码已发送至 {phone_number}</p>
                </div>
                <div>
                    <label for="code" class="block text-sm font-medium text-gray-700">请输入验证码</label>
                    <input type="text" name="code" id="code" required placeholder="12345"
                           class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                </div>
                <div>
                    <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700">
                        验证验证码
                    </button>
                </div>
            </form>
        """)
    except Exception as e:
        logger.exception("Failed to request code")
        return HTMLResponse(f"""
            <div class="bg-red-50 border-l-4 border-red-400 p-4 mb-4">
                <p class="text-sm text-red-700">错误: {str(e)}</p>
            </div>
            <button onclick="window.location.reload()" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gray-600 hover:bg-gray-700">
                重新开始
            </button>
        """)

@router.post("/accounts/{account_id}/login/phone/verify-code")
async def verify_phone_code(
    account_id: int,
    phone_code_hash: str = Form(...),
    code: str = Form(...),
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    try:
        res = await telegram_service.VerifyPhoneLoginCode(account_id, phone_code_hash, code)
        if res.get("next_step") == "verify_password":
            return HTMLResponse(f"""
                <form hx-post="/web/accounts/{account_id}/login/phone/verify-password" hx-target="#login-flow-container" hx-swap="innerHTML" class="space-y-6">
                    <div class="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-4">
                        <p class="text-sm text-yellow-700">该账号启用了两步验证，请输入二级密码。</p>
                    </div>
                    <div>
                        <label for="password" class="block text-sm font-medium text-gray-700">二级密码</label>
                        <input type="password" name="password" id="password" required
                               class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                    </div>
                    <div>
                        <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700">
                            确认登录
                        </button>
                    </div>
                </form>
            """)
        
        # Next step is done
        response = Response()
        response.headers["HX-Redirect"] = "/web/accounts"
        return response
    except Exception as e:
        logger.exception("Failed to verify code")
        return HTMLResponse(f"""
            <div class="bg-red-50 border-l-4 border-red-400 p-4 mb-4">
                <p class="text-sm text-red-700">错误: {str(e)}</p>
            </div>
            <button onclick="window.location.reload()" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gray-600 hover:bg-gray-700">
                重新开始
            </button>
        """)

@router.post("/accounts/{account_id}/login/phone/verify-password")
async def verify_two_factor(
    account_id: int,
    password: str = Form(...),
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    try:
        await telegram_service.VerifyTwoFactorPassword(account_id, password)
        response = Response()
        response.headers["HX-Redirect"] = "/web/accounts"
        return response
    except Exception as e:
        logger.exception("Failed to verify 2FA password")
        return HTMLResponse(f"""
            <div class="bg-red-50 border-l-4 border-red-400 p-4 mb-4">
                <p class="text-sm text-red-700">错误: {str(e)}</p>
            </div>
            <button onclick="window.location.reload()" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gray-600 hover:bg-gray-700">
                重新开始
            </button>
        """)

@router.post("/accounts/login/session")
async def login_with_session(
    phone_number: str = Form(...),
    session_string: str = Form(...),
    proxy_id: str = Form(""),
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    pid = int(proxy_id) if proxy_id and proxy_id.strip() else None
    try:
        await telegram_service.CreateAccountWithSessionLogin(phone_number, session_string, proxy_id=pid)
        response = Response()
        response.headers["HX-Redirect"] = "/web/accounts"
        return response
    except Exception as e:
        logger.exception("Failed to login with session")
        return HTMLResponse(f"""
            <div class="bg-red-50 border-l-4 border-red-400 p-4 mb-4">
                <p class="text-sm text-red-700">导入失败: {str(e)}</p>
            </div>
            <button onclick="window.location.reload()" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gray-600 hover:bg-gray-700">
                重新开始
            </button>
        """)

@router.get("/accounts/{account_id}", response_class=HTMLResponse)
async def get_account_detail(
    request: Request,
    account_id: int,
    db_session: Session = Depends(get_db_session),
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    account = db_session.get(TelegramAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    proxy = db_session.get(ProxyInfo, account.proxy_id) if account.proxy_id else None
    
    conversations = []
    error_msg = None
    if account.is_online:
        try:
            conversations = await telegram_service.ListConversations(account_id)
        except Exception as e:
            logger.exception("Failed to load conversations")
            error_msg = f"会话加载失败: {str(e)}"
            
    return templates.TemplateResponse("accounts/detail.html", {
        "request": request,
        "user_id": user_id,
        "account": account,
        "proxy": proxy,
        "conversations": conversations,
        "error_msg": error_msg
    })

@router.post("/accounts/{account_id}/toggle-active")
async def toggle_active(
    account_id: int,
    db_session: Session = Depends(get_db_session),
    user_id: int = Depends(get_current_user_from_cookie),
):
    account = db_session.get(TelegramAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    account.is_active = not account.is_active
    db_session.commit()
    
    label = "● 启用中" if account.is_active else "○ 已禁用"
    color_class = "text-green-600 font-bold" if account.is_active else "text-red-500 font-bold"
    
    return HTMLResponse(f"""
        <button id="status-badge-{account_id}"
                hx-post="/web/accounts/{account_id}/toggle-active"
                hx-target="#status-badge-{account_id}"
                hx-swap="outerHTML"
                class="inline-flex items-center px-3 py-1.5 border border-gray-300 shadow-sm text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50">
            <span class="{color_class}">{label}</span>
        </button>
    """)

@router.post("/accounts/{account_id}/delete")
async def delete_account(
    account_id: int,
    request: Request,
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    try:
        telegram_service.SoftDeleteAccount(account_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    if "HX-Request" in request.headers:
        response = Response()
        response.headers["HX-Redirect"] = "/web/accounts"
        return response
    return RedirectResponse("/web/accounts", status_code=303)

@router.post("/accounts/{account_id}/online")
async def online_account(
    account_id: int,
    request: Request,
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    try:
        await telegram_service.EnsureAccountOnline(account_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    if "HX-Request" in request.headers:
        response = Response()
        response.headers["HX-Redirect"] = f"/web/accounts/{account_id}"
        return response
    return RedirectResponse(f"/web/accounts/{account_id}", status_code=303)
```

---

### Task 3: Create Web Accounts Integration Tests

**Files:**
- Create: `tests/test_web_accounts.py`

- [ ] **Step 1: Write mock tests for routes**

Write standard pytest tests using `TestClient` to verify response codes and HTML elements.

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_telegram_service
from app.models.account import TelegramAccount, ProxyInfo
from app.web.dependencies import get_current_user_from_cookie
from main import create_api_application
from app.config import get_settings

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
    service.SoftDeleteAccount = MagicMock(return_value={"account_id": 42, "deleted": True})
    service.EnsureAccountOnline = AsyncMock(return_value={"account_id": 42, "is_online": True})
    service.ListConversations = AsyncMock(return_value=[
        {"id": "conv_1", "title": "Test Group", "type": "group", "unread_count": 0}
    ])
    return service

@pytest.fixture
def client(db_session, mock_telegram_service):
    app = create_api_application(get_settings())
    
    # Setup dependency overrides
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_telegram_service] = lambda: mock_telegram_service
    
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

def test_list_accounts_page(client, db_session: Session):
    # Setup test accounts
    acc = TelegramAccount(
        phone_number="+8613800001111",
        display_name="Test Account",
        is_active=True,
        is_online=True
    )
    db_session.add(acc)
    db_session.commit()
    
    response = client.get("/web/accounts")
    assert response.status_code == 200
    assert "+8613800001111" in response.text
    assert "Test Account" in response.text

def test_new_accounts_page(client):
    response = client.get("/web/accounts/new")
    assert response.status_code == 200
    assert "手机验证码登录" in response.text
    assert "直接导入 Session 字符串" in response.text

def test_request_phone_code(client, mock_telegram_service):
    response = client.post("/web/accounts/login/phone/request-code", data={
        "phone_number": "+8613800001111",
        "proxy_id": ""
    })
    assert response.status_code == 200
    assert "dummy_hash" in response.text
    mock_telegram_service.RequestPhoneLoginCode.assert_called_once_with("+8613800001111", proxy_id=None)

def test_verify_phone_code_done(client, mock_telegram_service):
    response = client.post("/web/accounts/42/login/phone/verify-code", data={
        "phone_code_hash": "dummy_hash",
        "code": "12345"
    })
    assert response.status_code == 200
    assert response.headers.get("HX-Redirect") == "/web/accounts"
    mock_telegram_service.VerifyPhoneLoginCode.assert_called_once_with(42, "dummy_hash", "12345")

def test_verify_phone_code_2fa(client, mock_telegram_service):
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

def test_verify_two_factor(client, mock_telegram_service):
    response = client.post("/web/accounts/42/login/phone/verify-password", data={
        "password": "mypassword"
    })
    assert response.status_code == 200
    assert response.headers.get("HX-Redirect") == "/web/accounts"
    mock_telegram_service.VerifyTwoFactorPassword.assert_called_once_with(42, "mypassword")

def test_login_with_session(client, mock_telegram_service):
    response = client.post("/web/accounts/login/session", data={
        "phone_number": "+8613800001111",
        "session_string": "dummy_session",
        "proxy_id": ""
    })
    assert response.status_code == 200
    assert response.headers.get("HX-Redirect") == "/web/accounts"
    mock_telegram_service.CreateAccountWithSessionLogin.assert_called_once_with("+8613800001111", "dummy_session", proxy_id=None)

def test_account_detail(client, db_session: Session):
    acc = TelegramAccount(
        phone_number="+8613800001111",
        display_name="Test Account",
        is_active=True,
        is_online=True
    )
    db_session.add(acc)
    db_session.commit()
    
    response = client.get(f"/web/accounts/{acc.id}")
    assert response.status_code == 200
    assert "+8613800001111" in response.text
    assert "Test Group" in response.text

def test_toggle_active(client, db_session: Session):
    acc = TelegramAccount(
        phone_number="+8613800001111",
        is_active=True
    )
    db_session.add(acc)
    db_session.commit()
    
    response = client.post(f"/web/accounts/{acc.id}/toggle-active")
    assert response.status_code == 200
    assert "已禁用" in response.text
    
    # Reload and check
    db_session.refresh(acc)
    assert acc.is_active is False

def test_delete_account(client, mock_telegram_service):
    response = client.post("/web/accounts/42/delete")
    assert response.status_code == 303
    mock_telegram_service.SoftDeleteAccount.assert_called_once_with(42)

def test_online_account(client, mock_telegram_service):
    response = client.post("/web/accounts/42/online")
    assert response.status_code == 303
    mock_telegram_service.EnsureAccountOnline.assert_called_once_with(42)
```
