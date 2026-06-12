from collections.abc import Sequence
from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    """仓储基类（async 版本，PR #11 收尾后唯一实现）。

    说明：
    1. PR #1-#10 阶段：与同步 ``BaseRepository`` 共存；
    2. PR #11 收尾：删 sync 版，本类统一为全链路 async 唯一实现（命名沿用原 sync 名以减少引用点改动）；
    3. 业务查询方法在具体 repository 中按 JPA 风格命名。
    """

    def __init__(self, session: AsyncSession, model_type: type[ModelT]) -> None:
        self._session = session
        self._model_type = model_type

    async def Save(self, entity: ModelT) -> ModelT:
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def SaveAll(self, entities: Sequence[ModelT]) -> Sequence[ModelT]:
        self._session.add_all(list(entities))
        await self._session.flush()
        return entities
