"""AuthService.RegisterUser 校验逻辑单元测试。

覆盖新增的邮箱正则校验与密码长度下限（6 位）逻辑。"""

import pytest

from app.config import Settings
from app.models.user import User
from app.repository.user_repository import UserRepository
from app.service.auth_service import AuthService


class FakeUserRepository(UserRepository):
    """仅实现 RegisterUser 所需方法的轻量仓储，继承 UserRepository ABC 以满足静态检查。

    Save 时模拟数据库自增主键赋值（真实 SQLAlchemy flush 也会自动给 id 赋值）。"""

    def __init__(self, existing_emails: set[str] | None = None) -> None:
        self._existing = set(existing_emails or ())
        self.saved: list[User] = []
        self._next_id = 1

    def ExistsByEmail(self, email: str) -> bool:
        return email in self._existing

    def Save(self, entity: User) -> User:
        if entity.id is None:
            entity.id = self._next_id
            self._next_id += 1
        self.saved.append(entity)
        return entity

    def FindById(self, user_id: int) -> User | None:
        raise NotImplementedError

    def FindByEmail(self, email: str) -> User | None:
        raise NotImplementedError

    def FindByApiKey(self, api_key: str) -> User | None:
        raise NotImplementedError

    def ExistsByApiKey(self, api_key: str) -> bool:
        raise NotImplementedError


class FakeSession:
    """记录 commit 调用、不连真实数据库的伪 Session。"""

    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


def _build_service(existing_emails: set[str] | None = None) -> tuple[AuthService, FakeUserRepository, FakeSession]:
    settings = Settings(jwt_secret_key="unit-test-secret")
    repo = FakeUserRepository(existing_emails=existing_emails)
    session = FakeSession()
    # AuthService.__init__ 形参声明为 SqlAlchemyUserRepository/Session 具体类型；
    # 运行时按 duck-typing 接受 Fake，但需 type: ignore 抑制静态检查。
    # session 形参声明为 sqlalchemy.orm.Session 具体类型，FakeSession 走 duck-typing 需 type: ignore
    service = AuthService(settings, session, repo)  # type: ignore[arg-type]
    return service, repo, session


# ---------- 邮箱格式校验 ----------

@pytest.mark.parametrize(
    "email",
    [
        "demo@example.com",
        "a.b+tag@sub.example.co",
        "name_123@example-domain.org",
    ],
)
def test_register_accepts_valid_email(email: str) -> None:
    service, _, _ = _build_service()
    result = service.RegisterUser(email=email, password="Password123")
    assert result["email"] == email.strip().lower()
    assert result["is_active"] is True


@pytest.mark.parametrize(
    "email",
    [
        "",
        "abc",
        "abc@",
        "@example.com",
        "abc@example",
        "abc@.com",
        "abc@example.",
        "abc example.com",
        "..@example.com",
        "a..b@example.com",
        ".@example.com",
        "a.@example.com",
    ],
)
def test_register_rejects_malformed_email(email: str) -> None:
    service, repo, session = _build_service()
    with pytest.raises(ValueError, match="邮箱格式不合法"):
        service.RegisterUser(email=email, password="Password123")
    assert repo.saved == []
    assert session.commits == 0


def test_register_normalizes_email_case_and_whitespace() -> None:
    service, repo, _ = _build_service()
    result = service.RegisterUser(email="  Demo@Example.COM  ", password="Password123")
    assert result["email"] == "demo@example.com"
    assert len(repo.saved) == 1
    assert repo.saved[0].email == "demo@example.com"


# ---------- 密码长度校验 ----------

def test_register_accepts_six_char_password() -> None:
    service, repo, _ = _build_service()
    result = service.RegisterUser(email="demo@example.com", password="abcdef")
    assert result["email"] == "demo@example.com"
    assert result["is_active"] is True
    assert len(repo.saved) == 1


def test_register_rejects_five_char_password() -> None:
    service, repo, session = _build_service()
    with pytest.raises(ValueError, match="密码长度需在 6-128 位之间"):
        service.RegisterUser(email="demo@example.com", password="abcde")
    assert repo.saved == []
    assert session.commits == 0


def test_register_accepts_max_length_password() -> None:
    service, repo, _ = _build_service()
    password = "a" * 128
    service.RegisterUser(email="demo@example.com", password=password)
    assert len(repo.saved) == 1


def test_register_rejects_over_max_length_password() -> None:
    service, repo, session = _build_service()
    with pytest.raises(ValueError, match="密码长度需在 6-128 位之间"):
        service.RegisterUser(email="demo@example.com", password="a" * 129)
    assert repo.saved == []
    assert session.commits == 0


# ---------- 邮箱已存在 ----------

def test_register_rejects_duplicate_email() -> None:
    service, repo, session = _build_service(existing_emails={"demo@example.com"})
    with pytest.raises(ValueError, match="邮箱已注册"):
        service.RegisterUser(email="Demo@Example.com", password="Password123")
    assert repo.saved == []
    assert session.commits == 0


# ---------- 校验顺序：邮箱格式应在密码长度之前 ----------

def test_register_validates_email_before_password() -> None:
    """两个字段都不合法时，邮箱错误先抛出（短路）。"""
    service, repo, session = _build_service()
    with pytest.raises(ValueError, match="邮箱格式不合法"):
        service.RegisterUser(email="not-an-email", password="abc")
    assert repo.saved == []
    assert session.commits == 0
