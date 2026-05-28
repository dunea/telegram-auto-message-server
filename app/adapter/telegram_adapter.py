import importlib
import asyncio
import json
from datetime import datetime
from typing import Any

from app.config import Settings


class TelegramAdapter:
    """Telethon 适配器。

    通过动态导入隔离第三方 SDK，避免业务层直接依赖 Telethon 细节。
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client_cache: dict[int, dict[str, Any]] = {}
        self._cache_recycled_count = 0
        self._cache_calls_count = 0

    def _log_cache_event(self, event: str, **fields: object) -> None:
        payload = {
            "ts": datetime.utcnow().isoformat(),
            "level": "INFO",
            "component": "telegram_adapter",
            "event": event,
            **fields,
        }
        print(json.dumps(payload, ensure_ascii=False))

    def _should_log_cache_stats(self) -> bool:
        interval = max(1, int(self._settings.pool_client_cache_stats_interval))
        return self._cache_calls_count % interval == 0

    def _emit_cache_stats_if_needed(self) -> None:
        if not self._should_log_cache_stats():
            return
        self._log_cache_event(
            "cache_stats",
            cached_clients=len(self._client_cache),
            recycled_clients=self._cache_recycled_count,
            cache_calls=self._cache_calls_count,
        )

    async def _call_with_timeout(self, coro: Any) -> Any:
        return await asyncio.wait_for(coro, timeout=self._settings.pool_login_timeout_seconds)

    async def _drop_client(self, account_id: int) -> None:
        cached = self._client_cache.pop(account_id, None)
        if not cached:
            return

        self._cache_recycled_count += 1

        client = cached.get("client")
        if client is None:
            return

        try:
            if await self._is_client_connected(client):
                await self._call_with_timeout(client.disconnect())
        except Exception:
            return

    async def _recycle_idle_client_if_needed(self, account_id: int) -> None:
        cached = self._client_cache.get(account_id)
        if not cached:
            return

        last_used_at = cached.get("last_used_at")
        if not isinstance(last_used_at, datetime):
            await self._drop_client(account_id)
            return

        idle_seconds = (datetime.utcnow() - last_used_at).total_seconds()
        if idle_seconds >= self._settings.pool_client_idle_ttl_seconds:
            await self._drop_client(account_id)

    def _should_force_rebuild_client(self, account_id: int) -> bool:
        cached = self._client_cache.get(account_id)
        if not cached:
            return False
        failed_count = int(cached.get("failed_count") or 0)
        return failed_count >= int(self._settings.pool_client_max_failed_count)

    def _mark_client_used(self, account_id: int) -> None:
        cached = self._client_cache.get(account_id)
        if not cached:
            return
        cached["last_used_at"] = datetime.utcnow()
        cached["failed_count"] = 0

    def _mark_client_failed(self, account_id: int) -> None:
        cached = self._client_cache.get(account_id)
        if not cached:
            return
        cached["failed_count"] = int(cached.get("failed_count") or 0) + 1
        cached["last_used_at"] = datetime.utcnow()

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
        self._cache_calls_count += 1
        await self._recycle_idle_client_if_needed(account_id)

        cached = self._client_cache.get(account_id)
        if cached is None:
            client = self._build_client(session_string=session_string)
            cached = {
                "client": client,
                "last_used_at": datetime.utcnow(),
                "failed_count": 0,
            }
            self._client_cache[account_id] = cached

        client = cached["client"]

        try:
            connected = await self._call_with_timeout(self._is_client_connected(client))
            if not connected:
                await self._call_with_timeout(client.connect())
            self._mark_client_used(account_id)
            self._emit_cache_stats_if_needed()
            return client
        except Exception:
            self._mark_client_failed(account_id)
            if self._should_force_rebuild_client(account_id):
                await self._drop_client(account_id)
            self._emit_cache_stats_if_needed()
            raise

    def _extract_peer(self, peer: Any) -> tuple[str, int | None]:
        if peer is None:
            return "unknown", None

        for field_name, peer_type in (("user_id", "user"), ("chat_id", "chat"), ("channel_id", "channel")):
            value = getattr(peer, field_name, None)
            if value is not None:
                return peer_type, int(value)
        return "unknown", None

    def _extract_reply_to_msg_id(self, message: Any) -> int | None:
        reply_to = getattr(message, "reply_to", None)
        if reply_to is None:
            return None
        reply_id = getattr(reply_to, "reply_to_msg_id", None)
        if reply_id is None:
            return None
        return int(reply_id)

    async def IsAuthorized(self, account_id: int, session_string: str) -> bool:
        client = await self.EnsureConnected(account_id=account_id, session_string=session_string)
        try:
            is_authorized = bool(await self._call_with_timeout(client.is_user_authorized()))
            self._mark_client_used(account_id)
            self._emit_cache_stats_if_needed()
            return is_authorized
        except Exception:
            self._mark_client_failed(account_id)
            if self._should_force_rebuild_client(account_id):
                await self._drop_client(account_id)
            self._emit_cache_stats_if_needed()
            raise

    async def ListDialogs(self, account_id: int, session_string: str, limit: int) -> list[dict[str, Any]]:
        client = await self.EnsureConnected(account_id=account_id, session_string=session_string)
        dialogs = await self._call_with_timeout(client.get_dialogs(limit=limit))

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
        entity = await self._call_with_timeout(client.get_entity(target_identifier))
        messages = await self._call_with_timeout(client.get_messages(entity, limit=limit))

        result: list[dict[str, Any]] = []
        for message in messages:
            message_date = getattr(message, "date", None)
            peer_type, peer_id = self._extract_peer(getattr(message, "peer_id", None))
            grouped_id = getattr(message, "grouped_id", None)
            forward_from = getattr(message, "forward", None)
            forward_sender = getattr(forward_from, "from_id", None)
            _, forward_from_user_id = self._extract_peer(forward_sender)

            result.append(
                {
                    "message_id": int(getattr(message, "id", 0) or 0),
                    "sender_id": int(getattr(message, "sender_id", 0) or 0),
                    "text": str(getattr(message, "message", "") or ""),
                    "date": message_date.isoformat() if isinstance(message_date, datetime) else None,
                    "grouped_id": int(grouped_id) if grouped_id is not None else None,
                    "peer_type": peer_type,
                    "peer_id": peer_id,
                    "reply_to_message_id": self._extract_reply_to_msg_id(message),
                    "forward_from_user_id": forward_from_user_id,
                }
            )
        return result

    async def SendMessage(
        self,
        account_id: int,
        session_string: str,
        target_identifier: str,
        content: str,
        media_url: str | None = None,
        media_caption: str | None = None,
    ) -> dict[str, Any]:
        client = await self.EnsureConnected(account_id=account_id, session_string=session_string)
        if media_url:
            sent_message = await self._call_with_timeout(
                client.send_file(target_identifier, media_url, caption=media_caption or content or "")
            )
        else:
            sent_message = await self._call_with_timeout(client.send_message(target_identifier, content))

        sent_date = getattr(sent_message, "date", None)
        peer_type, peer_id = self._extract_peer(getattr(sent_message, "peer_id", None))
        grouped_id = getattr(sent_message, "grouped_id", None)
        return {
            "message_id": int(getattr(sent_message, "id", 0) or 0),
            "target_identifier": target_identifier,
            "content": content,
            "date": sent_date.isoformat() if isinstance(sent_date, datetime) else None,
            "grouped_id": int(grouped_id) if grouped_id is not None else None,
            "peer_type": peer_type,
            "peer_id": peer_id,
            "reply_to_message_id": self._extract_reply_to_msg_id(sent_message),
            "sender_id": int(getattr(sent_message, "sender_id", 0) or 0),
        }
