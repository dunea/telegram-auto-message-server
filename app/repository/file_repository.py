from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.file import FileRecord
from app.repository.base_repository import BaseRepository


class FileRecordRepository(ABC):
    @abstractmethod
    def FindAllByStatus(self, status: str) -> list[FileRecord]:
        raise NotImplementedError

    @abstractmethod
    def DeleteById(self, file_id: int) -> None:
        raise NotImplementedError


class SqlAlchemyFileRecordRepository(BaseRepository[FileRecord], FileRecordRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session=session, model_type=FileRecord)

    def FindAllByStatus(self, status: str) -> list[FileRecord]:
        stmt = select(FileRecord).where(FileRecord.status == status)
        return list(self._session.scalars(stmt).all())

    def DeleteById(self, file_id: int) -> None:
        file_record = self._session.get(FileRecord, file_id)
        if file_record is not None:
            self._session.delete(file_record)
