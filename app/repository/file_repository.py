from abc import ABC, abstractmethod
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import FileRecord
from app.repository.base_repository import BaseRepository


class FileRecordRepository(ABC):
    """文件仓储接口（异步版本，PR #4 引入）。

    与 ``FileRecordRepository`` 并存到 PR #11 收尾。
    """

    @abstractmethod
    async def FindById(self, file_id: int) -> FileRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def FindAllByStatus(
        self,
        status: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[FileRecord]:
        raise NotImplementedError

    @abstractmethod
    async def FindAllByStatusAndExpiresAtBefore(self, status: str, expires_before: datetime, limit: int) -> list[FileRecord]:
        raise NotImplementedError

    @abstractmethod
    async def FindAllOrderByIdDesc(self, limit: int, offset: int, status: str | None = None, owner_user_id: int | None = None) -> list[FileRecord]:
        raise NotImplementedError

    @abstractmethod
    async def CountByStatus(self, status: str | None = None, owner_user_id: int | None = None) -> int:
        raise NotImplementedError

    @abstractmethod
    async def UpdateStatusById(self, file_id: int, status: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def DeleteById(self, file_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def ExistsByIdAndOwnerUserId(self, file_id: int, user_id: int) -> bool:
        raise NotImplementedError


class SqlAlchemyFileRecordRepository(BaseRepository[FileRecord], FileRecordRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_type=FileRecord)

    async def FindById(self, file_id: int) -> FileRecord | None:
        return await self._session.get(FileRecord, file_id)

    async def FindAllByStatus(
        self,
        status: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[FileRecord]:
        stmt = select(FileRecord).where(FileRecord.status == status)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        return list((await self._session.scalars(stmt)).all())

    async def FindAllByStatusAndExpiresAtBefore(self, status: str, expires_before: datetime, limit: int) -> list[FileRecord]:
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
        return list((await self._session.scalars(stmt)).all())

    async def FindAllOrderByIdDesc(self, limit: int, offset: int, status: str | None = None, owner_user_id: int | None = None) -> list[FileRecord]:
        stmt = select(FileRecord).order_by(FileRecord.id.desc()).offset(offset).limit(limit)
        if status:
            stmt = stmt.where(FileRecord.status == status)
        if owner_user_id is not None:
            stmt = stmt.where(FileRecord.owner_user_id == owner_user_id)
        return list((await self._session.scalars(stmt)).all())

    async def CountByStatus(self, status: str | None = None, owner_user_id: int | None = None) -> int:
        stmt = select(func.count(FileRecord.id))
        if status:
            stmt = stmt.where(FileRecord.status == status)
        if owner_user_id is not None:
            stmt = stmt.where(FileRecord.owner_user_id == owner_user_id)
        return int((await self._session.scalar(stmt)) or 0)

    async def UpdateStatusById(self, file_id: int, status: str) -> bool:
        file_record = await self.FindById(file_id)
        if file_record is None:
            return False
        file_record.status = status
        await self._session.flush()
        return True

    async def DeleteById(self, file_id: int) -> None:
        file_record = await self._session.get(FileRecord, file_id)
        if file_record is not None:
            await self._session.delete(file_record)

    async def ExistsByIdAndOwnerUserId(self, file_id: int, user_id: int) -> bool:
        stmt = select(FileRecord.id).where(
            FileRecord.id == file_id,
            FileRecord.owner_user_id == user_id
        )
        return (await self._session.scalar(stmt)) is not None
