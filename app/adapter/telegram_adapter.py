import importlib
from datetime import datetime
from typing import Any

from app.config import Settings


class TelegramAdapter:
    """Telethon 适配器。

    通过动态导入隔离第三方 SDK，避免业务层直接依赖 Telethon 细节。
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client_cache: dict[int, Any] = {}

    def _build_client(self, session_string: str) -> Any:
        telethon_module = importlib.import_module("telethon")
        sessions_module = importlib.import_module("telethon.sessions")

        telegram_client = getattr(telethon_module, "TelegramClient")
        string_session = getattr(sessions_module, "StringSession")

        if self._settings.telegram_api_id <= 0 or not self._settings.telegram_api_hash:
            raise ValueError("telegram_api_id 或 telegram_api_hash 未配置")

        session = string_session(session_string or "")
        return telegram_client(session, self._settings.telegram_api_id, self._settings.telegram_api_hash)

    async def _is_client_connected(self, client: Any) -> bool:
        connection_state = client.is_connected()
        if hasattr(connection_state, "__await__"):
            return bool(await connection_state)
        return bool(connection_state)

    async def EnsureConnected(self, account_id: int, session_string: str) -> Any:
        """确保指定账号对应客户端可用并保持连接。"""
        client = self._client_cache.get(account_id)
        if client is None:
            client = self._build_client(session_string=session_string)
            self._client_cache[account_id] = client

        if not await self._is_client_connected(client):
            await client.connect()
        return client

    async def IsAuthorized(self, account_id: int, session_string: str) -> bool:
        client = await self.EnsureConnected(account_id=account_id, session_string=session_string)
        return bool(await client.is_user_authorized())

    async def ListDialogs(self, account_id: int, session_string: str, limit: int) -> list[dict[str, Any]]:
        client = await self.EnsureConnected(account_id=account_id, session_string=session_string)
        dialogs = await client.get_dialogs(limit=limit)

        result: list[dict[str, Any]] = []
        for dialog in dialogs:
            result.append(
                {
                    "dialog_id": int(getattr(dialog, "id", 0) or 0),
                    "title": str(getattr(dialog, "title", "") or ""),
                    "username": str(getattr(getattr(dialog, "entity", None), "username", "") or ""),
                    "unread_count": int(getattr(dialog, "unread_count", 0) or 0),
                }
            )
        return result

    async def ListMessages(
        self,
        account_id: int,
        session_string: str,
        target_identifier: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        client = await self.EnsureConnected(account_id=account_id, session_string=session_string)
        entity = await client.get_entity(target_identifier)
        messages = await client.get_messages(entity, limit=limit)

        result: list[dict[str, Any]] = []
        for message in messages:
            message_date = getattr(message, "date", None)
            result.append(
                {
                    "message_id": int(getattr(message, "id", 0) or 0),
                    "sender_id": int(getattr(message, "sender_id", 0) or 0),
                    "text": str(getattr(message, "message", "") or ""),
                    "date": message_date.isoformat() if isinstance(message_date, datetime) else None,
                }
            )
        return result

    async def SendMessage(
        self,
        account_id: int,
        session_string: str,
        target_identifier: str,
        content: str,
    ) -> dict[str, Any]:
        client = await self.EnsureConnected(account_id=account_id, session_string=session_string)
        sent_message = await client.send_message(target_identifier, content)

        sent_date = getattr(sent_message, "date", None)
        return {
            "message_id": int(getattr(sent_message, "id", 0) or 0),
            "target_identifier": target_identifier,
            "content": content,
            "date": sent_date.isoformat() if isinstance(sent_date, datetime) else None,
        }
