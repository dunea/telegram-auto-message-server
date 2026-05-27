from collections.abc import Sequence
from typing import Generic, TypeVar

from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    """仓储基类。

    说明：
    1. 仅封装最基础的会话与实体类型。
    2. 业务查询方法在具体 repository 中按 JPA 风格命名。
    """

    def __init__(self, session: Session, model_type: type[ModelT]) -> None:
        self._session = session
        self._model_type = model_type

    def Save(self, entity: ModelT) -> ModelT:
        self._session.add(entity)
        self._session.flush()
        return entity

    def SaveAll(self, entities: Sequence[ModelT]) -> Sequence[ModelT]:
        self._session.add_all(list(entities))
        self._session.flush()
        return entities
