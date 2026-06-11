# 定时消息任务 CRUD 页面与路由 (Task 6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完善定时消息任务的 Web CRUD 页面和后端路由，实现关联账号、Cron表达式、多媒体附件、会话范围等配置并配有高颜值前端、HTMX启停，以及全套测试覆盖。

**Architecture:** 
1. 完善并确保 `app/web/routes/scheduled.py` 的路由调用 `TaskService` 执行定时任务的增删改查。
2. 创建高颜值的 Tailwind CSS 定时任务表单模板 `templates/scheduled/form.html`。
3. 实现全面的 `tests/test_web_scheduled.py` 测试套件，并通过运行 `pytest` 校验所有的功能点和边界。

**Tech Stack:** FastAPI, Jinja2, HTMX, Tailwind CSS, SQLAlchemy, Pytest

---

### Task 1: 创建高颜值定时任务表单模板

**Files:**
- Create: `templates/scheduled/form.html`

- [ ] **Step 1: 编写 `templates/scheduled/form.html` 模板内容**

```html
{% extends "base.html" %}
{% block title %}{% if task %}编辑{% else %}创建{% endif %}定时发送任务 - TG 自动消息服务{% endblock %}
{% block content %}
<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
    <!-- Back Navigation -->
    <div class="mb-4">
        <a href="/web/scheduled" class="inline-flex items-center text-sm font-medium text-indigo-600 hover:text-indigo-500">
            <svg class="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            返回列表
        </a>
    </div>

    <!-- Card -->
    <div class="bg-white shadow overflow-hidden sm:rounded-lg">
        <div class="px-6 py-5 border-b border-gray-200 bg-gray-50">
            <h3 class="text-lg leading-6 font-semibold text-gray-900">
                {% if task %}修改定时发送任务{% else %}新增定时发送任务{% endif %}
            </h3>
            <p class="mt-1 max-w-2xl text-sm text-gray-500">
                创建或编辑通过 Cron 表达式触发的固定发送计划
            </p>
        </div>

        <form action="{% if task %}/web/scheduled/{{ task.task_id }}/edit{% else %}/web/scheduled/new{% endif %}" method="POST" class="p-6 space-y-6">
            <!-- 托管账号 -->
            <div>
                <label for="account_id" class="block text-sm font-medium text-gray-700">关联托管账号 <span class="text-red-500">*</span></label>
                <select id="account_id" name="account_id" required 
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm {% if task %}bg-gray-100{% endif %}"
                        {% if task %}disabled{% endif %}>
                    <option value="">-- 请选择账号 --</option>
                    {% for acc in accounts %}
                    <option value="{{ acc.id }}" {% if task and task.account_id|string == acc.id|string %}selected{% endif %}>
                        {{ acc.display_name or acc.phone_number }} (ID: {{ acc.id }})
                    </option>
                    {% endfor %}
                </select>
                {% if task %}
                <!-- 编辑模式下由于 select 禁用，我们传递隐藏的 input 作为真正的表单传参 -->
                <input type="hidden" name="account_id" value="{{ task.account_id }}">
                {% endif %}
            </div>

            <!-- Cron 表达式及快捷选项 -->
            <div>
                <label for="cron_expr" class="block text-sm font-medium text-gray-700">Cron 表达式 <span class="text-red-500">*</span></label>
                <input type="text" name="cron_expr" id="cron_expr" required
                       value="{{ task.cron_expr if task else '' }}"
                       placeholder="如: */5 * * * * "
                       class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                
                <!-- 快捷选项 -->
                <div class="mt-2 flex flex-wrap gap-2">
                    <span class="text-xs text-gray-500 self-center">快捷选项:</span>
                    <button type="button" onclick="setCron('*/5 * * * *')" class="px-2 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs rounded transition">
                        每5分钟 (*/5 * * * *)
                    </button>
                    <button type="button" onclick="setCron('0 * * * *')" class="px-2 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs rounded transition">
                        每小时 (0 * * * *)
                    </button>
                    <button type="button" onclick="setCron('0 9 * * *')" class="px-2 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs rounded transition">
                        每天上午9点 (0 9 * * *)
                    </button>
                    <button type="button" onclick="setCron('0 18 * * *')" class="px-2 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs rounded transition">
                        每天下午6点 (0 18 * * *)
                    </button>
                </div>
                <p class="mt-1.5 text-xs text-gray-400">标准 5 段或 6 段 Cron 表达式（分、时、日、月、周）。</p>
            </div>

            <!-- 目标会话标识 -->
            <div>
                <label for="target_identifier" class="block text-sm font-medium text-gray-700">默认目标会话标识 <span class="text-red-500">*</span></label>
                <input type="text" name="target_identifier" id="target_identifier" required
                       value="{{ task.target_identifier if task else '' }}"
                       placeholder="用户名(如 @channel_name) 或 会话 ID(如 -10012345678)"
                       class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                <p class="mt-1 text-xs text-gray-400">默认消息发送的目标群组、频道或私聊 ID/用户名。</p>
            </div>

            <!-- 范围选择 (全选 / 指定会话) -->
            <div>
                <label for="scope_mode" class="block text-sm font-medium text-gray-700">会话响应范围 <span class="text-red-500">*</span></label>
                <select id="scope_mode" name="scope_mode" onchange="toggleScopeFields()" required
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                    <option value="all" {% if task and task.scope_mode == "all" %}selected{% endif %}>发送到默认目标会话</option>
                    <option value="specific" {% if task and task.scope_mode == "specific" %}selected{% endif %}>轮询发送到指定会话列表</option>
                </select>
            </div>

            <!-- 指定会话 ID -->
            <div id="scope-fields-container" class="border border-orange-50 p-4 rounded bg-orange-50/30">
                <label for="conversation_ids" class="block text-sm font-medium text-gray-700">指定会话 ID (以英文逗号 , 隔开) <span class="text-red-500">*</span></label>
                <input type="text" name="conversation_ids" id="conversation_ids" 
                       value="{{ conv_ids_str if task else '' }}"
                       placeholder="比如: 123456789, -100234567890"
                       class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                <p class="mt-1 text-xs text-gray-400">将在此列表内轮询/随机选择会话进行发送。群组 ID 通常以 -100 开头。</p>
            </div>

            <!-- 消息文本模板 -->
            <div>
                <label for="message_template" class="block text-sm font-medium text-gray-700">消息发送文本模板</label>
                <textarea id="message_template" name="message_template" rows="4"
                          placeholder="配置您要定时发送的文本消息..."
                          class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">{{ task.message_template if task else '' }}</textarea>
            </div>

            <!-- 图片或文件附件选择 -->
            <div>
                <label for="file_id" class="block text-sm font-medium text-gray-700">媒体文件附件 (可选)</label>
                <select id="file_id" name="file_id" 
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                    <option value="">-- 无附件 --</option>
                    {% for file in files %}
                    <option value="{{ file.id }}" {% if selected_file_id|string == file.id|string %}selected{% endif %}>
                        {{ file.local_path }} (ID: {{ file.id }})
                    </option>
                    {% endfor %}
                </select>
                <p class="mt-1 text-xs text-gray-400">选择一个已上传至服务器的图片、文件。支持与文本模板结合发送。</p>
            </div>

            <!-- Form Actions -->
            <div class="flex justify-end gap-3 pt-4 border-t border-gray-200">
                <a href="/web/scheduled" class="inline-flex justify-center items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 shadow-sm transition">
                    取消
                </a>
                <button type="submit" class="inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm transition">
                    保存定时发送任务
                </button>
            </div>
        </form>
    </div>
</div>

<script>
// 设置 Cron 快捷输入
function setCron(val) {
    document.getElementById('cron_expr').value = val;
}

// 动态切换会话范围字段
function toggleScopeFields() {
    const scopeMode = document.getElementById('scope_mode').value;
    const container = document.getElementById('scope-fields-container');
    const input = document.getElementById('conversation_ids');
    
    if (scopeMode === 'specific') {
        container.style.display = 'block';
        input.required = true;
    } else {
        container.style.display = 'none';
        input.required = false;
    }
}

// 初始页面挂载
document.addEventListener("DOMContentLoaded", function() {
    toggleScopeFields();
});
</script>
{% endblock %}
```

- [ ] **Step 2: 验证模板渲染正确。无需启动服务器，我们将在编写路由与测试后一并测试。**

---

### Task 2: 完善与校准定时路由

**Files:**
- Modify: `app/web/routes/scheduled.py`

- [ ] **Step 1: 检查 `app/web/routes/scheduled.py` 中所有的引入、依赖声明、逻辑完整性**

由于该路由已大致存在，我们需要细致对齐：
- `Depends(get_current_user_from_cookie)`。
- 对 `file_id` 和附件类型的处理：
  ```python
  ext = file_rec.local_path.lower().split(".")[-1] if "." in file_rec.local_path else ""
  media_type = "image" if ext in ["jpg", "jpeg", "png", "gif", "webp"] else "file"
  ```
- 确保没有语法错误，特别是 `edit` 中的：
  ```python
  from app.models.message import MessageContent
  ```
  该引用在 FastAPI 异步请求中可被正常解析。

---

### Task 3: 编写定时任务 Web 路由单元测试

**Files:**
- Create: `tests/test_web_scheduled.py`

- [ ] **Step 1: 编写 `tests/test_web_scheduled.py`，充分覆盖：**
  - 未登录用户的重定向逻辑
  - 任务列表展示（包括空列表及携带账号与过滤逻辑的数据列表）
  - 创建页面加载
  - 正常创建文本任务，以及携带文件上传的高级创建任务
  - 编辑页面加载并成功更新
  - HTMX 局部状态启停开关 (`/web/scheduled/{task_id}/toggle-active`)
  - 软删除任务逻辑

```python
"""定时消息任务 Web 页面与路由单元测试。"""

import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session, get_task_service
from app.models.base import Base
from app.models.account import TelegramAccount
from app.models.file import FileRecord
from app.models.task import ScheduledMessageTask
from app.models.message import MessageContent
from app.web.dependencies import get_current_user_from_cookie
from app.web.routes.scheduled import router as scheduled_router


# 设置内存数据库
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


from sqlalchemy import event

@event.listens_for(Base, "before_insert", propagate=True)
def set_id_if_null(mapper, connection, target):
    if hasattr(target, "id") and getattr(target, "id", None) is None:
        import random
        setattr(target, "id", random.randint(10000, 99999999))


def get_testing_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前清空并重新创建表。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


class FakeTaskScheduler:
    def AddOrReplaceCronJob(self, job_id, cron_expr, callback, args=None):
        pass
    def RemoveJob(self, job_id):
        pass


class FakeTaskService:
    def __init__(self, db: Session):
        self.db = db
        # 依赖其它的 Repository 结构，如果用 Fake 的话，我们就根据路由需求 mock。
        # 另外，我们也可以直接在 Dependency override 中覆盖 get_task_service，构造真实的 TaskService 或简单的 Fake。
        # 这里为了配合真实落库校验，我们可以实例化真实的 TaskService，或是极简包装它。
        pass

# 为了最大限度保障数据库与 TaskService 的集成，我们写一个支持真实落库并 Mock 掉底层 Telegram / Scheduler 交互的 Service
def get_testing_task_service(db: Session = Depends(get_testing_db)):
    from app.service.task_service import TaskService
    from app.config import get_settings
    from app.repository.message_repository import (
        SqlAlchemyMessageContentRepository,
        SqlAlchemyMessageContentMediaRepository,
    )
    from app.repository.task_repository import (
        SqlAlchemyScheduledMessageTaskRepository,
        SqlAlchemyRuleMessageTaskRepository,
        SqlAlchemyTaskExecutionLogRepository,
    )
    settings = get_settings()
    scheduler = FakeTaskScheduler()
    return TaskService(
        settings=settings,
        session=db,
        session_factory=TestingSessionLocal,
        scheduler=scheduler,
        telegram_adapter=None, # mock adapter
        message_content_repository=SqlAlchemyMessageContentRepository(db),
        message_content_media_repository=SqlAlchemyMessageContentMediaRepository(db),
        scheduled_task_repository=SqlAlchemyScheduledMessageTaskRepository(db),
        rule_task_repository=SqlAlchemyRuleMessageTaskRepository(db),
        task_execution_log_repository=SqlAlchemyTaskExecutionLogRepository(db),
    )


def test_scheduled_unauthenticated() -> None:
    """测试未登录用户访问定时任务页面被重定向。"""
    app = FastAPI()
    app.include_router(scheduled_router)
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    resp = client.get("/web/scheduled", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/login"


def test_scheduled_list_empty() -> None:
    """测试已登录用户访问没有定时任务的列表。"""
    app = FastAPI()
    app.include_router(scheduled_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    app.dependency_overrides[get_task_service] = get_testing_task_service
    
    client = TestClient(app)
    resp = client.get("/web/scheduled")
    assert resp.status_code == 200
    assert "定时消息任务" in resp.text
    assert "暂无任何定时消息任务" in resp.text


def test_scheduled_list_with_data() -> None:
    """测试已登录用户访问定时任务列表。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    task = ScheduledMessageTask(id=1, account_id=1, cron_expr="*/5 * * * *", target_identifier="@test_group", message_template="Hello world", is_active=True)
    db.add_all([acc, task])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(scheduled_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    app.dependency_overrides[get_task_service] = get_testing_task_service
    
    client = TestClient(app)
    resp = client.get("/web/scheduled")
    assert resp.status_code == 200
    assert "测试账号" in resp.text
    assert "*/5 * * * *" in resp.text
    assert "Hello world" in resp.text


def test_scheduled_list_filter() -> None:
    """测试已登录用户访问定时任务列表并按账号过滤。"""
    db = TestingSessionLocal()
    acc1 = TelegramAccount(id=1, phone_number="+8612345678901", display_name="账号1", is_active=True)
    acc2 = TelegramAccount(id=2, phone_number="+8612345678902", display_name="账号2", is_active=True)
    task1 = ScheduledMessageTask(id=1, account_id=1, cron_expr="*/5 * * * *", target_identifier="@test_group", message_template="Task 1", is_active=True)
    task2 = ScheduledMessageTask(id=2, account_id=2, cron_expr="0 9 * * *", target_identifier="@another_group", message_template="Task 2", is_active=True)
    db.add_all([acc1, acc2, task1, task2])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(scheduled_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    app.dependency_overrides[get_task_service] = get_testing_task_service
    
    client = TestClient(app)
    # 仅展示账号1
    resp = client.get("/web/scheduled?account_id=1")
    assert resp.status_code == 200
    assert "Task 1" in resp.text
    assert "Task 2" not in resp.text


def test_scheduled_new_page() -> None:
    """测试加载创建任务页面。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    file_rec = FileRecord(id=1, local_path="temp/pic.jpg", status="uploaded", file_size_bytes=2048)
    db.add_all([acc, file_rec])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(scheduled_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    resp = client.get("/web/scheduled/new")
    assert resp.status_code == 200
    assert "新增定时发送任务" in resp.text
    assert "测试账号" in resp.text
    assert "temp/pic.jpg" in resp.text


def test_scheduled_create_simple() -> None:
    """测试创建简单文本定时发送任务。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    db.add(acc)
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(scheduled_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    app.dependency_overrides[get_task_service] = get_testing_task_service
    
    client = TestClient(app)
    form_data = {
        "account_id": 1,
        "cron_expr": "*/10 * * * *",
        "target_identifier": "@my_group",
        "message_template": "Scheduled Text",
        "scope_mode": "all",
        "conversation_ids": "",
        "file_id": ""
    }
    resp = client.post("/web/scheduled/new", data=form_data, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/scheduled"
    
    db = TestingSessionLocal()
    task = db.scalar(select(ScheduledMessageTask).where(ScheduledMessageTask.message_template == "Scheduled Text"))
    assert task is not None
    assert task.cron_expr == "*/10 * * * *"
    assert task.target_identifier == "@my_group"
    db.close()


def test_scheduled_create_with_media() -> None:
    """测试创建携带多媒体附件的复杂定时任务。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    file_rec = FileRecord(id=88, local_path="temp/photo.jpg", status="uploaded", file_size_bytes=100)
    db.add_all([acc, file_rec])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(scheduled_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    app.dependency_overrides[get_task_service] = get_testing_task_service
    
    client = TestClient(app)
    form_data = {
        "account_id": 1,
        "cron_expr": "0 12 * * *",
        "target_identifier": "@media_channel",
        "message_template": "Media Caption",
        "scope_mode": "specific",
        "conversation_ids": "11111,22222",
        "file_id": "88"
    }
    resp = client.post("/web/scheduled/new", data=form_data, follow_redirects=False)
    assert resp.status_code == 303
    
    db = TestingSessionLocal()
    task = db.scalar(select(ScheduledMessageTask).where(ScheduledMessageTask.target_identifier == "@media_channel"))
    assert task is not None
    assert task.scope_mode == "specific"
    assert task.conversation_ids == [11111, 22222]
    
    # 验证 MessageContent
    content_obj = db.get(MessageContent, task.message_content_id)
    assert content_obj is not None
    assert content_obj.content_type.value == "media"
    assert content_obj.media_type.value == "image"
    assert content_obj.media_url == "temp/photo.jpg"
    assert content_obj.text_content == "Media Caption"
    db.close()


def test_scheduled_edit_page() -> None:
    """测试加载定时发送编辑页面。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    task = ScheduledMessageTask(id=5, account_id=1, cron_expr="0 9 * * *", target_identifier="@foo", message_template="edit text", is_active=True)
    db.add_all([acc, task])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(scheduled_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    app.dependency_overrides[get_task_service] = get_testing_task_service
    
    client = TestClient(app)
    resp = client.get("/web/scheduled/5/edit")
    assert resp.status_code == 200
    assert "修改定时发送任务" in resp.text
    assert "edit text" in resp.text
    assert "0 9 * * *" in resp.text


def test_scheduled_update_task() -> None:
    """测试更新定时发送任务。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    task = ScheduledMessageTask(id=5, account_id=1, cron_expr="0 9 * * *", target_identifier="@foo", message_template="before edit", is_active=True)
    db.add_all([acc, task])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(scheduled_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    app.dependency_overrides[get_task_service] = get_testing_task_service
    
    client = TestClient(app)
    form_data = {
        "account_id": 1,
        "cron_expr": "0 10 * * *",
        "target_identifier": "@bar",
        "message_template": "after edit",
        "scope_mode": "all",
        "conversation_ids": "",
        "file_id": ""
    }
    resp = client.post("/web/scheduled/5/edit", data=form_data, follow_redirects=False)
    assert resp.status_code == 303
    
    db = TestingSessionLocal()
    updated_task = db.get(ScheduledMessageTask, 5)
    assert updated_task is not None
    assert updated_task.cron_expr == "0 10 * * *"
    assert updated_task.target_identifier == "@bar"
    assert updated_task.message_template == "after edit"
    db.close()


def test_scheduled_toggle_active() -> None:
    """测试 HTMX 切换启用状态。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    task = ScheduledMessageTask(id=12, account_id=1, cron_expr="0 9 * * *", target_identifier="@foo", message_template="active toggle", is_active=True)
    db.add_all([acc, task])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(scheduled_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    app.dependency_overrides[get_task_service] = get_testing_task_service
    
    client = TestClient(app)
    resp = client.post("/web/scheduled/12/toggle-active")
    assert resp.status_code == 200
    assert "已禁用" in resp.text
    
    db = TestingSessionLocal()
    updated_task = db.get(ScheduledMessageTask, 12)
    assert updated_task is not None
    assert updated_task.is_active is False
    db.close()


def test_scheduled_delete() -> None:
    """测试软删除。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    task = ScheduledMessageTask(id=15, account_id=1, cron_expr="0 9 * * *", target_identifier="@foo", message_template="to delete", is_active=True)
    db.add_all([acc, task])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(scheduled_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    app.dependency_overrides[get_task_service] = get_testing_task_service
    
    client = TestClient(app)
    resp = client.post("/web/scheduled/15/delete", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/scheduled"
    
    db = TestingSessionLocal()
    deleted_task = db.get(ScheduledMessageTask, 15)
    assert deleted_task is not None
    assert deleted_task.is_active is False
    db.close()
```

- [ ] **Step 2: 运行测试并确证**

Run: `pytest tests/test_web_scheduled.py -v`
Expected: 100% Passed.

---

### Task 4: 执行全量 pytest 校验

- [ ] **Step 1: 运行项目中的全量 pytest 进行无副作用回归测试**

Run: `pytest`
Expected: All tests pass.
