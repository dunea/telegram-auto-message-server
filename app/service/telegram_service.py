from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.adapter.telegram_adapter import TelegramAdapter
from app.config import Settings
from app.models.account import TelegramAccount
from app.models.message import TelegramMessage
from app.repository.account_repository import SqlAlchemyTelegramAccountRepository
from app.repository.message_repository import SqlAlchemyTelegramMessageRepository


class TelegramService:
    """Telegram 核心能力服务。"""

    def __init__(
        self,
        settings: Settings,
        session: Session,
        account_repository: SqlAlchemyTelegramAccountRepository,
        message_repository: SqlAlchemyTelegramMessageRepository,
        telegram_adapter: TelegramAdapter,
    ) -> None:
        self._settings = settings
        self._session = session
        self._account_repository = account_repository
        self._message_repository = message_repository
        self._telegram_adapter = telegram_adapter

    def _get_account_or_raise(self, account_id: int) -> TelegramAccount:
        account = self._account_repository.FindById(account_id)
        if account is None:
            raise ValueError("账号不存在")
        return account

    def CreateAccount(self, phone_number: str, proxy_id: int | None, session_string: str | None) -> dict[str, Any]:
        """创建托管账号。"""
        if self._account_repository.ExistsByPhoneNumber(phone_number):
            raise ValueError("手机号已存在")

        account = TelegramAccount(
            phone_number=phone_number,
            session_string=session_string or "",
            proxy_id=proxy_id,
            is_active=True,
            is_online=False,
        )
        self._account_repository.Save(account)
        self._session.commit()
        return {
            "account_id": int(account.id),
            "phone_number": account.phone_number,
            "is_active": bool(account.is_active),
            "is_online": bool(account.is_online),
        }

    def ListManagedAccounts(self) -> list[dict[str, Any]]:
        """获取托管账号列表。"""
        accounts = self._account_repository.FindAllByIsActive(True)
        return [
            {
                "account_id": int(account.id),
                "phone_number": account.phone_number,
                "display_name": account.display_name,
                "is_active": bool(account.is_active),
                "is_online": bool(account.is_online),
                "proxy_id": account.proxy_id,
            }
            for account in accounts
        ]

    def UpdateAccountSessionString(self, account_id: int, session_string: str) -> None:
        account = self._get_account_or_raise(account_id)
        account.session_string = session_string
        self._session.commit()

    async def EnsureAccountOnline(self, account_id: int) -> dict[str, Any]:
        """检查账号授权并刷新在线状态。"""
        account = self._get_account_or_raise(account_id)
        is_authorized = await self._telegram_adapter.IsAuthorized(
            account_id=int(account.id),
            session_string=account.session_string,
        )
        account.is_online = bool(is_authorized)
        self._session.commit()
        return {
            "account_id": int(account.id),
            "is_online": bool(account.is_online),
            "is_active": bool(account.is_active),
        }

    async def ListConversations(self, account_id: int, limit: int = 50) -> list[dict[str, Any]]:
        """获取指定账号的会话列表。"""
        account = self._get_account_or_raise(account_id)
        return await self._telegram_adapter.ListDialogs(
            account_id=int(account.id),
            session_string=account.session_string,
            limit=limit,
        )

    async def ListMessages(self, account_id: int, target_identifier: str, limit: int = 50) -> list[dict[str, Any]]:
        """获取指定目标会话的消息列表。"""
        account = self._get_account_or_raise(account_id)
        return await self._telegram_adapter.ListMessages(
            account_id=int(account.id),
            session_string=account.session_string,
            target_identifier=target_identifier,
            limit=limit,
        )

    def ListSendRecords(self, account_id: int, limit: int = 50) -> list[dict[str, Any]]:
        """获取发送记录。"""
        records = self._message_repository.FindAllByAccountIdOrderByIdDesc(account_id=account_id, limit=limit)
        return [
            {
                "id": int(record.id),
                "account_id": int(record.account_id),
                "conversation_id": record.conversation_id,
                "conversation_peer": record.conversation_peer,
                "content": record.content,
                "status": record.status,
                "telegram_message_id": record.telegram_message_id,
                "sent_at": record.sent_at.isoformat() if record.sent_at else None,
            }
            for record in records
        ]

    async def SendMessage(self, account_id: int, target_identifier: str, content: str) -> dict[str, Any]:
        """发送消息并落库结果。"""
        account = self._get_account_or_raise(account_id)
        conversation_id: int | None = int(target_identifier) if target_identifier.isdigit() else None

        try:
            sent_result = await self._telegram_adapter.SendMessage(
                account_id=int(account.id),
                session_string=account.session_string,
                target_identifier=target_identifier,
                content=content,
            )

            message_record = TelegramMessage(
                account_id=int(account.id),
                conversation_id=conversation_id,
                conversation_peer=target_identifier,
                direction="out",
                content=content,
                status="sent",
                telegram_message_id=sent_result.get("message_id"),
                sent_at=datetime.utcnow(),
            )
            self._message_repository.Save(message_record)
            self._session.commit()

            return {
                "account_id": int(account.id),
                "target_identifier": target_identifier,
                "content": content,
                "status": "sent",
                "telegram_message_id": sent_result.get("message_id"),
                "error": None,
            }
        except Exception as exc:
            message_record = TelegramMessage(
                account_id=int(account.id),
                conversation_id=conversation_id,
                conversation_peer=target_identifier,
                direction="out",
                content=content,
                status="failed",
                telegram_message_id=None,
                sent_at=datetime.utcnow(),
            )
            self._message_repository.Save(message_record)
            self._session.commit()
            return {
                "account_id": int(account.id),
                "target_identifier": target_identifier,
                "content": content,
                "status": "failed",
                "telegram_message_id": None,
                "error": str(exc),
            }
