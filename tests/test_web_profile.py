import pytest
from fastapi import FastAPI, Depends, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from passlib.context import CryptContext
import jwt

from app.api.deps import get_db_session, get_auth_service
from app.web.dependencies import get_current_user_from_cookie
from app.web.routes.profile import router as profile_router
from app.models.base import Base
from app.models.user import User
from app.config import get_settings
from app.service.auth_service import AuthService
from app.repository.user_repository import SqlAlchemyUserRepository

_PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Setup memory SQLite DB
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class _FakeAsyncSession:
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
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def get_testing_auth_service(db_session=Depends(get_testing_db)):
    settings = get_settings()
    user_repo = SqlAlchemyUserRepository(db_session)
    return AuthService(settings=settings, session=db_session, user_repository=user_repo)


def _build_profile_client(current_user_id: int | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(profile_router)
    app.dependency_overrides[get_db_session] = get_testing_db
    app.dependency_overrides[get_auth_service] = get_testing_auth_service
    if current_user_id is not None:
        app.dependency_overrides[get_current_user_from_cookie] = lambda: current_user_id
    return TestClient(app)


def test_profile_page_unauthenticated() -> None:
    client = _build_profile_client()
    resp = client.get("/web/profile", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/login"


def test_profile_page_authenticated() -> None:
    db = TestingSessionLocal()
    user = User(
        id=1,
        email="test@example.com",
        password_hash=_PASSWORD_CONTEXT.hash("Password123"),
        api_key="test-api-key-123",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.close()

    client = _build_profile_client(current_user_id=1)

    resp = client.get("/web/profile")
    assert resp.status_code == 200
    assert "个人资料" in resp.text
    assert "test@example.com" in resp.text
    assert "test-api-key-123" in resp.text


def test_profile_change_email_success() -> None:
    db = TestingSessionLocal()
    user = User(
        id=1,
        email="test@example.com",
        password_hash=_PASSWORD_CONTEXT.hash("Password123"),
        api_key="test-api-key-123",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.close()

    client = _build_profile_client(current_user_id=1)

    resp = client.post(
        "/web/profile/email",
        data={"new_email": "newemail@example.com"},
        follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/profile?email_success=true"
    assert "web_token" in resp.cookies

    # Verify token payload
    token = resp.cookies["web_token"]
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    assert payload["email"] == "newemail@example.com"
    assert int(payload["sub"]) == 1

    # Verify db update
    db = TestingSessionLocal()
    updated_user = db.get(User, 1)
    assert updated_user.email == "newemail@example.com"
    db.close()


def test_profile_change_email_invalid_format() -> None:
    db = TestingSessionLocal()
    user = User(
        id=1,
        email="test@example.com",
        password_hash=_PASSWORD_CONTEXT.hash("Password123"),
        api_key="test-api-key-123",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.close()

    client = _build_profile_client(current_user_id=1)

    resp = client.post(
        "/web/profile/email",
        data={"new_email": "invalid-email-format"},
        follow_redirects=False
    )
    assert resp.status_code == 200
    assert "邮箱格式不合法" in resp.text


def test_profile_change_email_duplicate() -> None:
    db = TestingSessionLocal()
    user1 = User(
        id=1,
        email="test1@example.com",
        password_hash=_PASSWORD_CONTEXT.hash("Password123"),
        api_key="key1",
        is_active=True
    )
    user2 = User(
        id=2,
        email="test2@example.com",
        password_hash=_PASSWORD_CONTEXT.hash("Password123"),
        api_key="key2",
        is_active=True
    )
    db.add_all([user1, user2])
    db.commit()
    db.close()

    client = _build_profile_client(current_user_id=1)

    resp = client.post(
        "/web/profile/email",
        data={"new_email": "test2@example.com"},
        follow_redirects=False
    )
    assert resp.status_code == 200
    assert "该邮箱已被其他用户使用" in resp.text


def test_profile_change_password_success() -> None:
    db = TestingSessionLocal()
    user = User(
        id=1,
        email="test@example.com",
        password_hash=_PASSWORD_CONTEXT.hash("OldPassword123"),
        api_key="test-api-key-123",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.close()

    client = _build_profile_client(current_user_id=1)

    resp = client.post(
        "/web/profile/password",
        data={"old_password": "OldPassword123", "new_password": "NewPassword123"},
        follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/web/profile?password_success=true"
    assert "web_token" in resp.cookies

    # Verify db update
    db = TestingSessionLocal()
    updated_user = db.get(User, 1)
    assert _PASSWORD_CONTEXT.verify("NewPassword123", updated_user.password_hash)
    db.close()


def test_profile_change_password_incorrect_old() -> None:
    db = TestingSessionLocal()
    user = User(
        id=1,
        email="test@example.com",
        password_hash=_PASSWORD_CONTEXT.hash("OldPassword123"),
        api_key="test-api-key-123",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.close()

    client = _build_profile_client(current_user_id=1)

    resp = client.post(
        "/web/profile/password",
        data={"old_password": "WrongOldPassword", "new_password": "NewPassword123"},
        follow_redirects=False
    )
    assert resp.status_code == 200
    assert "原密码不正确" in resp.text


def test_profile_change_password_invalid_length() -> None:
    db = TestingSessionLocal()
    user = User(
        id=1,
        email="test@example.com",
        password_hash=_PASSWORD_CONTEXT.hash("OldPassword123"),
        api_key="test-api-key-123",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.close()

    client = _build_profile_client(current_user_id=1)

    resp = client.post(
        "/web/profile/password",
        data={"old_password": "OldPassword123", "new_password": "short"},
        follow_redirects=False
    )
    assert resp.status_code == 200
    assert "新密码长度需在 6-128 位之间" in resp.text
