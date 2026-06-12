# PR #3 · 阶段 3：users + 新 AsyncBaseRepository

## 目标

把 Auth/User 子系统迁为 async，并引入 `AsyncBaseRepository` 作为后续所有 repository 的基类。

## 改动文件清单

| 文件 | 类型 | 改动点 |
|------|------|--------|
| `app/repository/base_repository.py` | 修改 | **新增** `AsyncBaseRepository`（与 `BaseRepository` 并存），含 `Save` / `SaveAll` 两个 async 方法 |
| `app/repository/user_repository.py` | 修改 | 整文件改 async；`SqlAlchemyUserRepository.__init__(self, session: AsyncSession)`；所有方法 `await session.execute/scalar/scalars` |
| `app/service/auth_service.py` | 修改 | 9 个方法全部改 `async def`；构造函数 `session: AsyncSession`；`self._session.commit/flush` → `await`；passlib 哈希保留在 async（CPU bound 单次 <100ms） |
| `app/api/routes/users.py` | 修改 | 4 个路由改 `async def`；Depends 改 `get_async_db_session` |
| `app/api/deps.py` | 修改 | 新增 `get_async_auth_service` 工厂函数（构造时注入 `AsyncSession` 版的 `UserRepository` 与 `AuthService`） |

## 关键代码骨架

### `app/repository/base_repository.py` 末尾追加

```python
from sqlalchemy.ext.asyncio import AsyncSession


class AsyncBaseRepository:
    """异步基类仓储。

    与 ``BaseRepository`` 并存，阶段 1-10 期间同步/异步 repository 共存。
    阶段 11 收尾时统一下线同步基类。
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def Save(self, entity) -> None:
        self._session.add(entity)
        await self._session.flush()

    async def SaveAll(self, entities) -> None:
        self._session.add_all(entities)
        await self._session.flush()
```

### `app/repository/user_repository.py` 关键方法

```python
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.repository.base_repository import AsyncBaseRepository


class SqlAlchemyUserRepository(AsyncBaseRepository):
    async def FindByEmail(self, email: str):
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def FindById(self, user_id: int):
        return await self._session.get(User, user_id)

    async def ExistsByEmail(self, email: str) -> bool:
        stmt = select(func.count()).select_from(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0
    # ... 其余 8 个方法同样改写
```

### `app/service/auth_service.py` 关键方法

```python
class AuthService:
    def __init__(
        self,
        settings: Settings,
        session: AsyncSession,
        user_repository: SqlAlchemyUserRepository,
    ) -> None: ...

    async def RegisterUser(self, email: str, password: str) -> User:
        if await self._user_repository.ExistsByEmail(email):
            raise ValueError("邮箱已注册")
        hashed = self._hash_password(password)
        user = User(email=email, password_hash=hashed)
        await self._user_repository.Save(user)
        await self._session.commit()
        return user

    async def LoginUser(self, email: str, password: str) -> str:
        user = await self._user_repository.FindByEmail(email)
        if user is None or not self._verify_password(password, user.password_hash):
            raise PermissionError("邮箱或密码错误")
        return self._issue_access_token(user)

    # 其余 7 个方法同样改 async
```

### `app/api/deps.py` 新增 `get_async_auth_service`

```python
async def get_async_auth_service(
    db_session: AsyncSession = Depends(get_async_db_session),
) -> AuthService:
    settings = get_settings()
    user_repository = SqlAlchemyUserRepository(db_session)
    return AuthService(
        settings=settings,
        session=db_session,
        user_repository=user_repository,
    )
```

### `app/api/routes/users.py`

```python
@router.post("/users", status_code=201)
async def register_user(
    payload: UserRegister,
    auth_service: AuthService = Depends(get_async_auth_service),
): ...
# 其余 3 个路由同样改 async
```

## 风险点

1. **passlib bcrypt 是 CPU bound**（~50ms），保留在 async 上下文可接受；**不**用 `to_thread`。
2. **JWT 编码/解码**（`jwt.encode/decode`）也是 CPU bound，保留在 async 即可。
3. **事务边界**：`AuthService` 内部既有 `commit` 也有外层路由调 commit，**统一在 service 内部 await commit**。
4. **`AsyncSession.expire_on_commit=False`** 已由 PR #1 在 factory 中设置，避免 commit 后访问属性触发隐式 IO。
5. **`get_current_user` 本 PR 不动**（仍走 sync auth_service 验证 JWT），阶段 11 统一处理（已与用户确认）。

## 验证步骤

```bash
python -m pytest -q --ignore=tests/e2e
python -m pytest -q tests/test_auth_service.py -v
python -m pytest -q tests/test_auth_placeholder.py -v
python -m pytest -q tests/test_web_auth.py -v
python -m pytest -q tests/e2e/test_auth.py
# 手动 smoke
curl -X POST http://127.0.0.1:8001/api/v1/users -d '{"email":"a@b.com","password":"x"}'
curl -X POST http://127.0.0.1:8001/api/v1/users/login -d '...'
```

## 回滚方案

`git revert <commit-sha-of-PR#3>`

## 完成判据

- [ ] `base_repository.py` 含 `AsyncBaseRepository`（与同步基类并存）
- [ ] `user_repository.py` 全部 11 个方法 async
- [ ] `auth_service.py` 全部 9 个方法 async
- [ ] `users.py` 4 个路由 async
- [ ] `deps.py` 含 `get_async_auth_service`（旧 `get_auth_service` 保留）
- [ ] `get_current_user` 未改动（保留 sync 验证 JWT 路径）
- [ ] `pytest -q` 全绿
- [ ] e2e `tests/e2e/test_auth.py` 全绿
- [ ] 手测注册/登录/刷新 token 通过
