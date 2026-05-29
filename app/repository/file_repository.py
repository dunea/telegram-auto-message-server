from abc import ABC, abstractmethod
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.file import FileRecord
from app.repository.base_repository import BaseRepository


class FileRecordRepository(ABC):
    @abstractmethod
    def FindById(self, file_id: int) -> FileRecord | None:
        raise NotImplementedError

    @abstractmethod
    def FindAllByStatus(self, status: str) -> list[FileRecord]:
        raise NotImplementedError

    @abstractmethod
    def FindAllByStatusAndExpiresAtBefore(self, status: str, expires_before: datetime, limit: int) -> list[FileRecord]:
        raise NotImplementedError

    @abstractmethod
    def FindAllOrderByIdDesc(self, limit: int, offset: int, status: str | None = None) -> list[FileRecord]:
        raise NotImplementedError

    @abstractmethod
    def CountByStatus(self, status: str | None = None) -> int:
        raise NotImplementedError

    @abstractmethod
    def UpdateStatusById(self, file_id: int, status: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def DeleteById(self, file_id: int) -> None:
        raise NotImplementedError


class SqlAlchemyFileRecordRepository(BaseRepository[FileRecord], FileRecordRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session=session, model_type=FileRecord)

    def FindById(self, file_id: int) -> FileRecord | None:
        stmt = select(FileRecord).where(FileRecord.id == file_id)
        return self._session.scalar(stmt)

    def FindAllByStatus(self, status: str) -> list[FileRecord]:
        stmt = select(FileRecord).where(FileRecord.status == status)
        return list(self._session.scalars(stmt).all())

    def FindAllByStatusAndExpiresAtBefore(self, status: str, expires_before: datetime, limit: int) -> list[FileRecord]:
        stmt = (
            select(FileRecord)
            .where(
                FileRecord.status == status,
                FileRecord.expires_at.is_not(None),
                FileRecord.expires_at <= expires_before,
            )
            .order_by(FileRecord.id.asc())
            .limit(max(1, int(limit)))
        )
        return list(self._session.scalars(stmt).all())

    def FindAllOrderByIdDesc(self, limit: int, offset: int, status: str | None = None) -> list[FileRecord]:
        stmt = select(FileRecord).order_by(FileRecord.id.desc()).offset(offset).limit(limit)
        if status:
            stmt = stmt.where(FileRecord.status == status)
        return list(self._session.scalars(stmt).all())

    def CountByStatus(self, status: str | None = None) -> int:
        stmt = select(func.count(FileRecord.id))
        if status:
            stmt = stmt.where(FileRecord.status == status)
        return int(self._session.scalar(stmt) or 0)

    def UpdateStatusById(self, file_id: int, status: str) -> bool:
        file_record = self.FindById(file_id)
        if file_record is None:
            return False
        file_record.status = status
        self._session.flush()
        return True

    def DeleteById(self, file_id: int) -> None:
        file_record = self._session.get(FileRecord, file_id)
        if file_record is not None:
            self._session.delete(file_record)
