"""定时消息任务 Web 页面与路由单元测试。"""

from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI, Depends
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
    scheduler = MagicMock()
    telegram_adapter = MagicMock()
    return TaskService(
        settings=settings,
        session=db,
        session_factory=TestingSessionLocal,
        scheduler=scheduler,  # type: ignore
        telegram_adapter=telegram_adapter,  # type: ignore
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
    # 绕过 LSP 对 Optional[Enum] 的分析并且兼容 String/Enum 类型
    content_type_raw = getattr(content_obj, "content_type")
    content_type_val = content_type_raw.value if hasattr(content_type_raw, "value") else content_type_raw
    
    media_type_raw = getattr(content_obj, "media_type")
    media_type_val = media_type_raw.value if media_type_raw and hasattr(media_type_raw, "value") else media_type_raw
    
    assert content_type_val == "media"
    assert media_type_val == "image"
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
