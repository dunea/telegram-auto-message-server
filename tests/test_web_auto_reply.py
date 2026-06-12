"""自动回复规则 Web 页面与路由单元测试。"""

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session, get_auto_reply_service
from app.models.base import Base
from app.models.account import TelegramAccount
from app.models.file import FileRecord
from app.models.task import AutoReplyRule
from app.web.dependencies import get_current_user_from_cookie
from app.web.routes.auto_reply import router as auto_reply_router


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


def test_auto_reply_unauthenticated() -> None:
    """测试未登录用户访问自动回复相关页面被重定向。"""
    app = FastAPI()
    app.include_router(auto_reply_router)
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    resp = client.get("/web/auto-reply", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/login"


def test_auto_reply_list_empty() -> None:
    """测试已登录用户访问没有规则的自动回复列表。"""
    app = FastAPI()
    app.include_router(auto_reply_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    resp = client.get("/web/auto-reply")
    assert resp.status_code == 200
    assert "自动回复规则" in resp.text
    assert "暂无任何自动回复规则" in resp.text


def test_auto_reply_list_with_data() -> None:
    """测试已登录用户访问包含规则和账号的自动回复列表。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    rule = AutoReplyRule(id=1, account_id=1, trigger_keyword="hello", reply_content="world", is_active=True, trigger_mode="keyword")
    db.add(acc)
    db.add(rule)
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(auto_reply_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    resp = client.get("/web/auto-reply")
    assert resp.status_code == 200
    assert "自动回复规则" in resp.text
    assert "测试账号" in resp.text
    assert "hello" in resp.text
    assert "world" in resp.text


def test_auto_reply_list_filter() -> None:
    """测试已登录用户访问自动回复列表并按照账号过滤。"""
    db = TestingSessionLocal()
    acc1 = TelegramAccount(id=1, phone_number="+8612345678901", display_name="账号1", is_active=True)
    acc2 = TelegramAccount(id=2, phone_number="+8612345678902", display_name="账号2", is_active=True)
    rule1 = AutoReplyRule(id=1, account_id=1, trigger_keyword="hello", reply_content="world", is_active=True, trigger_mode="keyword")
    rule2 = AutoReplyRule(id=2, account_id=2, trigger_keyword="apple", reply_content="banana", is_active=True, trigger_mode="keyword")
    db.add_all([acc1, acc2, rule1, rule2])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(auto_reply_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    
    # 过滤账号1
    resp = client.get("/web/auto-reply?account_id=1")
    assert resp.status_code == 200
    assert "hello" in resp.text
    assert "apple" not in resp.text


def test_auto_reply_new_page() -> None:
    """测试已登录用户访问新建规则页面。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    file_rec = FileRecord(id=1, local_path="temp/test.png", status="uploaded", file_size_bytes=1024)
    db.add_all([acc, file_rec])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(auto_reply_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    resp = client.get("/web/auto-reply/new")
    assert resp.status_code == 200
    assert "新增自动回复规则" in resp.text
    assert "测试账号" in resp.text
    assert "temp/test.png" in resp.text


def test_auto_reply_create_rule_simple() -> None:
    """测试提交最基本自动回复规则表单。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    db.add(acc)
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(auto_reply_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    form_data = {
        "account_id": 1,
        "trigger_mode": "keyword",
        "trigger_keyword": "abc",
        "keywords": "xyz, opq",
        "reply_content": "reply_abc",
        "scope_mode": "all",
        "conversation_ids": ""
    }
    resp = client.post("/web/auto-reply/new", data=form_data, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/auto-reply"
    
    # 验证规则确实落库
    db = TestingSessionLocal()
    rule = db.scalar(select(AutoReplyRule).where(AutoReplyRule.trigger_keyword == "abc"))
    assert rule is not None
    assert rule.reply_content == "reply_abc"
    assert rule.keywords == ["xyz", "opq"]
    db.close()


def test_auto_reply_create_rule_with_pool() -> None:
    """测试带有多消息池和附件的自动回复规则创建。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    file_rec = FileRecord(id=99, local_path="temp/photo.jpg", status="uploaded", file_size_bytes=100)
    db.add_all([acc, file_rec])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(auto_reply_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    
    # 构建重复 Form 字段
    form_data = {
        "account_id": "1",
        "trigger_mode": "keyword",
        "trigger_keyword": "pool_keyword",
        "keywords": "kw1",
        "reply_content": "",
        "scope_mode": "specific",
        "conversation_ids": "112233,-445566",
        "reply_messages_text": ["消息一", "消息二"],
        "reply_messages_file_id": ["", "99"],
    }
    
    resp = client.post("/web/auto-reply/new", data=form_data, follow_redirects=False)
    assert resp.status_code == 303
    
    # 验证规则和多消息级联保存
    db = TestingSessionLocal()
    rule = db.scalar(select(AutoReplyRule).where(AutoReplyRule.trigger_keyword == "pool_keyword"))
    assert rule is not None
    assert rule.scope_mode == "specific"
    assert rule.conversation_ids == [112233, -445566]
    
    # 验证消息池
    msgs = sorted(rule.reply_messages, key=lambda m: m.sort_order)
    assert len(msgs) == 2
    assert msgs[0].text == "消息一"
    assert len(msgs[0].media) == 0
    
    assert msgs[1].text == "消息二"
    assert len(msgs[1].media) == 1
    assert msgs[1].media[0].file_record_id == 99
    db.close()


def test_auto_reply_edit_page() -> None:
    """测试已登录用户访问编辑页面。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    rule = AutoReplyRule(id=1, account_id=1, trigger_keyword="edit_me", reply_content="some_content", is_active=True, trigger_mode="keyword")
    db.add_all([acc, rule])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(auto_reply_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    resp = client.get("/web/auto-reply/1/edit")
    assert resp.status_code == 200
    assert "修改自动回复规则" in resp.text
    assert "edit_me" in resp.text


def test_auto_reply_update_rule() -> None:
    """测试提交修改规则表单。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    rule = AutoReplyRule(id=10, account_id=1, trigger_keyword="before_edit", reply_content="before_content", is_active=True, trigger_mode="keyword")
    db.add_all([acc, rule])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(auto_reply_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    form_data = {
        "account_id": 1,
        "trigger_mode": "all",
        "trigger_keyword": "",
        "keywords": "",
        "reply_content": "after_content",
        "scope_mode": "all",
        "conversation_ids": ""
    }
    resp = client.post("/web/auto-reply/10/edit", data=form_data, follow_redirects=False)
    assert resp.status_code == 303
    
    db = TestingSessionLocal()
    rule_after = db.get(AutoReplyRule, 10)
    assert rule_after is not None
    assert rule_after.trigger_mode == "all"
    assert rule_after.reply_content == "after_content"
    db.close()


def test_auto_reply_toggle_active() -> None:
    """测试 HTMX 切换自动回复规则的启用/禁用状态。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    rule = AutoReplyRule(id=5, account_id=1, trigger_keyword="toggle", reply_content="ok", is_active=True, trigger_mode="keyword")
    db.add_all([acc, rule])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(auto_reply_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    resp = client.post("/web/auto-reply/5/toggle-active")
    assert resp.status_code == 200
    # 状态应该被切换成了 False (已禁用)
    assert "已禁用" in resp.text
    
    db = TestingSessionLocal()
    rule_after = db.get(AutoReplyRule, 5)
    assert rule_after is not None
    assert rule_after.is_active is False
    db.close()


def test_auto_reply_delete() -> None:
    """测试软删除自动回复规则。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    rule = AutoReplyRule(id=8, account_id=1, trigger_keyword="delete_me", reply_content="done", is_active=True, trigger_mode="keyword")
    db.add_all([acc, rule])
    db.commit()
    db.close()
    
    app = FastAPI()
    app.include_router(auto_reply_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db
    
    client = TestClient(app)
    resp = client.post("/web/auto-reply/8/delete", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/auto-reply"
    
    # 验证规则被软删除 (is_active 被置为 False)
    db = TestingSessionLocal()
    rule_after = db.get(AutoReplyRule, 8)
    assert rule_after is not None
    assert rule_after.is_active is False
    db.close()


def test_auto_reply_messages_page() -> None:
    """测试获取自动回复规则随机消息池管理页面。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    rule = AutoReplyRule(id=10, account_id=1, trigger_keyword="hello", reply_content="hi", is_active=True, trigger_mode="keyword")
    db.add_all([acc, rule])
    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(auto_reply_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db

    client = TestClient(app)
    resp = client.get("/web/auto-reply/10/messages")
    assert resp.status_code == 200
    assert "配置随机回复消息池" in resp.text
    assert "测试账号" in resp.text


def test_auto_reply_messages_update() -> None:
    """测试更新自动回复规则随机消息池。"""
    db = TestingSessionLocal()
    acc = TelegramAccount(id=1, phone_number="+8612345678901", display_name="测试账号", is_active=True)
    rule = AutoReplyRule(id=11, account_id=1, trigger_keyword="hello", reply_content="hi", is_active=True, trigger_mode="keyword")
    db.add_all([acc, rule])
    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(auto_reply_router)
    app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    app.dependency_overrides[get_db_session] = get_testing_db

    client = TestClient(app)
    payload = {
        "reply_messages_text": ["文本1", "文本2"],
        "reply_messages_file_id": ["", ""]
    }
    resp = client.post("/web/auto-reply/11/messages", data=payload, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/auto-reply"

    # 验证数据库中消息已被保存
    db = TestingSessionLocal()
    rule_after = db.scalars(select(AutoReplyRule).where(AutoReplyRule.id == 11)).first()
    assert rule_after is not None
    msgs = sorted(rule_after.reply_messages, key=lambda m: m.sort_order)
    assert len(msgs) == 2
    assert msgs[0].text == "文本1"
    assert msgs[1].text == "文本2"
    db.close()
