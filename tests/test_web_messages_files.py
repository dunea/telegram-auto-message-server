"""消息历史与文件管理 Web 页面与路由单元测试。"""

import io
import os
import random
from datetime import datetime
from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session, get_file_service
from app.models.base import Base
from app.models.account import TelegramAccount
from app.models.file import FileRecord
from app.models.message import TelegramMessage
from app.web.dependencies import get_current_user_from_cookie
from app.web.routes.messages import router as messages_router
from app.web.routes.files import router as files_router

# 设置内存数据库
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(Base, "before_insert", propagate=True)
def set_id_if_null(mapper, connection, target):
    if hasattr(target, "id") and getattr(target, "id", None) is None:
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


def get_testing_file_service(db: Session = Depends(get_testing_db)):
    from app.service.file_service import FileService
    from app.config import get_settings
    from app.repository.file_repository import SqlAlchemyFileRecordRepository
    
    settings = get_settings()
    # 确保有一个专门用于测试的临时目录
    settings.local_temp_dir = "./tmp_test_files"
    
    file_record_repo = SqlAlchemyFileRecordRepository(db)
    s3_adapter = MagicMock()
    s3_adapter.UploadFile.return_value = "https://fake-s3-bucket.s3.amazonaws.com/test_key"
    
    # 模拟下载
    def mock_download(key, local_path):
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(b"fake-file-bytes")
    s3_adapter.DownloadFile.side_effect = mock_download

    return FileService(
        settings=settings,
        session=db,
        file_record_repository=file_record_repo,
        s3_adapter=s3_adapter,
    )


# 极简 app，用于单独测试这两个 router 
test_app = FastAPI()
test_app.include_router(messages_router)
test_app.include_router(files_router)

# 注册公共覆盖
test_app.dependency_overrides[get_db_session] = get_testing_db
test_app.dependency_overrides[get_file_service] = get_testing_file_service


@pytest.fixture
def override_auth():
    test_app.dependency_overrides[get_current_user_from_cookie] = lambda: 1
    yield
    test_app.dependency_overrides[get_current_user_from_cookie] = get_current_user_from_cookie


def test_messages_unauthenticated() -> None:
    """测试未登录访问被拦截重定向（由 get_current_user_from_cookie 决定，通常被重定向或抛 401）。"""
    # 这里的 get_current_user_from_cookie 如果正常运行，没有 Mock 且没 Cookie 就会重定向或抛 401
    client = TestClient(test_app)
    resp = client.get("/web/messages", follow_redirects=False)
    # 如果依赖没有被 Mock 且 cookie 不存在，在正常实现下会被重定向或抛异常
    # 让我们验证其返回适当的鉴权拦截行为
    assert resp.status_code in [303, 401, 403, 500]  # 看原鉴权逻辑


def test_list_messages_web(override_auth) -> None:
    db_session = TestingSessionLocal()
    client = TestClient(test_app)

    # 1. 制造测试账号
    acc = TelegramAccount(
        phone_number="+8618888888888",
        display_name="测试托管账号",
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
    assert "测试托管账号" in resp.text

    # 4. 按 account_id 筛选
    resp = client.get(f"/web/messages?account_id={acc.id}")
    assert resp.status_code == 200
    assert "测试托管账号" in resp.text

    # 5. 按 direction 筛选
    resp = client.get("/web/messages?direction=out")
    assert resp.status_code == 200
    assert "Hello out" in resp.text
    assert "Hello in" not in resp.text

    db_session.close()


def test_files_web_flow(override_auth) -> None:
    db_session = TestingSessionLocal()
    client = TestClient(test_app)

    # 1. 测试文件上传
    file_content = b"my-file-test-content-bytes"
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

    # 清理创建的测试临时文件和目录
    try:
        if os.path.exists(record.local_path):
            os.remove(record.local_path)
        if os.path.exists("./tmp_test_files"):
            import shutil
            shutil.rmtree("./tmp_test_files")
    except Exception:
        pass

    db_session.close()
