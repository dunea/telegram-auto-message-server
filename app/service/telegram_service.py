from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from app.adapter.telegram_adapter import TelegramAdapter
from app.config import Settings
from app.models.account import TelegramAccount
from app.models.enums import (
    MessageAttemptStatus,
    MessageContentType,
    MessageDirection,
    MessageMediaType,
    MessageSendStatus,
    MessageSourceType,
    TelegramPeerType,
)
from app.models.message import (
    MessageContent,
    MessageContentMedia,
    TelegramMessage,
    TelegramMessageMedia,
    TelegramMessageSendAttempt,
)
from app.repository.account_repository import (
    SqlAlchemyTelegramAccountRepository,
)
from app.repository.message_repository import (
    SqlAlchemyMessageContentMediaRepository,
    SqlAlchemyMessageContentRepository,
    SqlAlchemyTelegramMessageMediaRepository,
    SqlAlchemyTelegramMessageRepository,
    SqlAlchemyTelegramMessageSendAttemptRepository,
    SqlAlchemyMessageContentMediaRepository,
    SqlAlchemyMessageContentRepository,
    SqlAlchemyTelegramMessageMediaRepository,
    SqlAlchemyTelegramMessageRepository,
    SqlAlchemyTelegramMessageSendAttemptRepository,
)

class TelegramService:
    """Telegram 服务（异步版本，PR #5 + PR #7 合并）。

    说明：
    1. 覆盖 messages（PR #5）+ accounts（PR #7）所有路由所需方法；
    2. 与 ``TelegramService``（同步）并存到 PR #11 收尾；
    3. pool_runner 与 web 路由仍用同步 ``TelegramService``；
    4. PR #7 阶段：``_get_account_or_raise`` 重构为通过 ``SqlAlchemyTelegramAccountRepository``。
    """

    def __init__(
        self,
        settings: Settings,
        session: AsyncSession,
        account_repository: SqlAlchemyTelegramAccountRepository,
        message_content_repository: SqlAlchemyMessageContentRepository,
        message_content_media_repository: SqlAlchemyMessageContentMediaRepository,
        message_repository: SqlAlchemyTelegramMessageRepository,
        message_media_repository: SqlAlchemyTelegramMessageMediaRepository,
        message_send_attempt_repository: SqlAlchemyTelegramMessageSendAttemptRepository,
        telegram_adapter: TelegramAdapter,
    ) -> None:
        self._settings = settings
        self._session = session
        self._account_repository = account_repository
        self._message_content_repository = message_content_repository
        self._message_content_media_repository = message_content_media_repository
        self._message_repository = message_repository
        self._message_media_repository = message_media_repository
        self._message_send_attempt_repository = message_send_attempt_repository
        self._telegram_adapter = telegram_adapter

    async def _get_account_or_raise(self, account_id: int) -> TelegramAccount:
        account = await self._account_repository.FindById(account_id)
        if account is None:
            raise ValueError("账号不存在")
        return account

    async def _get_account_by_phone_or_raise(self, phone_number: str) -> TelegramAccount:
        account = await self._account_repository.FindByPhoneNumber(phone_number)
        if account is None:
            raise ValueError("账号不存在")
        return account

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _normalize_content_type(value: MessageContentType | str | None) -> MessageContentType:
        if isinstance(value, MessageContentType):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for enum_item in MessageContentType:
                if enum_item.value == normalized:
                    return enum_item
        return MessageContentType.TEXT

    @staticmethod
    def _normalize_media_type(value: MessageMediaType | str | None) -> MessageMediaType | None:
        if value is None:
            return None
        if isinstance(value, MessageMediaType):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if not normalized:
                return None
            for enum_item in MessageMediaType:
                if enum_item.value == normalized:
                    return enum_item
        return None

    @staticmethod
    def _normalize_source_type(value: MessageSourceType | str | None) -> MessageSourceType:
        if isinstance(value, MessageSourceType):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for enum_item in MessageSourceType:
                if enum_item.value == normalized:
                    return enum_item
        return MessageSourceType.MANUAL

    @staticmethod
    def _normalize_peer_type(value: TelegramPeerType | str | None) -> TelegramPeerType:
        if isinstance(value, TelegramPeerType):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for enum_item in TelegramPeerType:
                if enum_item.value == normalized:
                    return enum_item
        return TelegramPeerType.UNKNOWN

    # ========== Accounts 路径（PR #7 新增） ==========

    async def CreateAccount(self, phone_number: str, proxy_id: int | None, session_string: str | None) -> dict[str, Any]:
        if await self._account_repository.ExistsByPhoneNumber(phone_number):
            raise ValueError("手机号已存在")
        account = TelegramAccount(
            phone_number=phone_number,
            session_string=session_string or "",
            proxy_id=proxy_id,
            is_active=True,
            is_online=False,
        )
        await self._account_repository.Save(account)
        await self._session.commit()
        return {
            "account_id": int(account.id),
            "phone_number": account.phone_number,
            "is_active": bool(account.is_active),
            "is_online": bool(account.is_online),
        }

    async def ListManagedAccounts(self) -> list[dict[str, Any]]:
        accounts = await self._account_repository.FindAll()
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

    async def RequestPhoneLoginCode(self, phone_number: str, proxy_id: int | None = None) -> dict[str, Any]:
        account = await self._account_repository.FindByPhoneNumber(phone_number)
        if account is None:
            await self.CreateAccount(phone_number=phone_number, proxy_id=proxy_id, session_string="")
            account = await self._get_account_by_phone_or_raise(phone_number)
        elif proxy_id is not None:
            account.proxy_id = proxy_id
            await self._session.flush()

        phone_code_hash = await self._telegram_adapter.RequestLoginCode(
            account_id=int(account.id),
            phone_number=account.phone_number,
            session_string=account.session_string or "",
        )
        await self._session.commit()
        return {
            "account_id": int(account.id),
            "phone_number": account.phone_number,
            "is_active": bool(account.is_active),
            "is_online": bool(account.is_online),
            "next_step": "verify_code",
            "message": "验证码已发送，请提交验证码。",
            "phone_code_hash": phone_code_hash,
        }

    async def VerifyPhoneLoginCode(self, account_id: int, phone_code_hash: str, code: str) -> dict[str, Any]:
        account = await self._get_account_or_raise(account_id)
        signed_in, need_password = await self._telegram_adapter.SignInWithCode(
            account_id=int(account.id),
            session_string=account.session_string or "",
            phone_number=account.phone_number,
            phone_code_hash=phone_code_hash,
            code=code,
        )

        if need_password:
            return {
                "account_id": int(account.id),
                "phone_number": account.phone_number,
                "is_active": bool(account.is_active),
                "is_online": bool(account.is_online),
                "next_step": "verify_password",
                "message": "账号开启了二级密码，请继续提交二级密码。",
            }

        if signed_in:
            await self._refresh_account_online_profile(account)

        return {
            "account_id": int(account.id),
            "phone_number": account.phone_number,
            "is_active": bool(account.is_active),
            "is_online": bool(account.is_online),
            "next_step": "done",
            "message": "账号登录成功。",
        }

    async def VerifyTwoFactorPassword(self, account_id: int, password: str) -> dict[str, Any]:
        account = await self._get_account_or_raise(account_id)
        await self._telegram_adapter.SignInWithPassword(
            account_id=int(account.id),
            session_string=account.session_string or "",
            password=password,
        )
        await self._refresh_account_online_profile(account)
        return {
            "account_id": int(account.id),
            "phone_number": account.phone_number,
            "is_active": bool(account.is_active),
            "is_online": bool(account.is_online),
            "next_step": "done",
            "message": "二级密码验证成功，账号已上线。",
        }

    async def CreateAccountWithSessionLogin(self, phone_number: str, session_string: str, proxy_id: int | None = None) -> dict[str, Any]:
        account = await self._account_repository.FindByPhoneNumber(phone_number)
        if account is None:
            await self.CreateAccount(phone_number=phone_number, proxy_id=proxy_id, session_string=session_string)
            account = await self._get_account_by_phone_or_raise(phone_number)
        else:
            account.session_string = session_string
            if proxy_id is not None:
                account.proxy_id = proxy_id
            account.is_active = True
            await self._session.flush()

        is_authorized = await self._telegram_adapter.IsAuthorized(
            account_id=int(account.id),
            session_string=account.session_string or "",
        )
        if not is_authorized:
            raise ValueError("session 无效，账号未完成授权")

        await self._refresh_account_online_profile(account)
        return {
            "account_id": int(account.id),
            "phone_number": account.phone_number,
            "is_active": bool(account.is_active),
            "is_online": bool(account.is_online),
            "next_step": "done",
            "message": "账号通过 session 登录成功。",
        }

    async def SetAccountActive(self, account_id: int, is_active: bool) -> dict[str, Any]:
        updated = await self._account_repository.UpdateIsActiveById(account_id=account_id, is_active=is_active)
        if not updated:
            raise ValueError("账号不存在")
        await self._session.commit()
        account = await self._get_account_or_raise(account_id)
        return {
            "account_id": int(account.id),
            "phone_number": account.phone_number,
            "is_active": bool(account.is_active),
            "is_online": bool(account.is_online),
        }

    async def SoftDeleteAccount(self, account_id: int) -> dict[str, Any]:
        result = await self.SetAccountActive(account_id=account_id, is_active=False)
        return {**result, "deleted": True}

    async def _refresh_account_online_profile(self, account: TelegramAccount) -> None:
        exported_session = await self._telegram_adapter.ExportSessionString(
            account_id=int(account.id),
            session_string=account.session_string or "",
        )
        profile = await self._telegram_adapter.GetSelfProfile(
            account_id=int(account.id),
            session_string=exported_session,
        )
        account.session_string = exported_session
        account.telegram_user_id = profile.get("telegram_user_id")
        account.display_name = profile.get("display_name")
        account.is_online = True
        account.is_active = True
        await self._session.commit()

    async def UpdateAccountSessionString(self, account_id: int, session_string: str) -> None:
        account = await self._get_account_or_raise(account_id)
        account.session_string = session_string
        await self._session.commit()

    async def EnsureAccountOnline(self, account_id: int) -> dict[str, Any]:
        account = await self._get_account_or_raise(account_id)
        is_authorized = await self._telegram_adapter.IsAuthorized(
            account_id=int(account.id),
            session_string=account.session_string,
        )
        account.is_online = bool(is_authorized)
        await self._session.commit()
        return {
            "account_id": int(account.id),
            "is_online": bool(account.is_online),
            "is_active": bool(account.is_active),
        }

    async def ListConversations(self, account_id: int, limit: int = 50) -> list[dict[str, Any]]:
        account = await self._get_account_or_raise(account_id)
        return await self._telegram_adapter.ListDialogs(
            account_id=int(account.id),
            session_string=account.session_string,
            limit=limit,
        )

    async def ListMessages(self, account_id: int, target_identifier: str, limit: int = 50) -> list[dict[str, Any]]:
        account = await self._get_account_or_raise(account_id)
        messages = await self._telegram_adapter.ListMessages(
            account_id=int(account.id),
            session_string=account.session_string,
            target_identifier=target_identifier,
            limit=limit,
        )

        account_telegram_user_id = int(account.telegram_user_id) if account.telegram_user_id else 0
        for item in messages:
            telegram_message_id = int(item.get("message_id") or 0)
            if telegram_message_id <= 0:
                continue

            existed = await self._message_repository.FindByAccountIdAndConversationPeerAndTelegramMessageId(
                account_id=int(account.id),
                conversation_peer=target_identifier,
                telegram_message_id=telegram_message_id,
            )
            if existed is not None:
                continue

            sender_id = int(item.get("sender_id") or 0)
            direction = MessageDirection.OUT if account_telegram_user_id and sender_id == account_telegram_user_id else MessageDirection.IN

            raw_date = item.get("date")
            message_at: datetime | None = None
            if isinstance(raw_date, str) and raw_date:
                try:
                    message_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                except ValueError:
                    message_at = None

            message_record = TelegramMessage(
                message_content_id=None,
                source_type=MessageSourceType.MANUAL,
                account_id=int(account.id),
                conversation_id=sender_id or None,
                conversation_peer=target_identifier,
                grouped_id=int(item.get("grouped_id")) if item.get("grouped_id") is not None else None,
                group_index=0,
                peer_type=self._normalize_peer_type(item.get("peer_type")),
                peer_id=int(item.get("peer_id")) if item.get("peer_id") is not None else None,
                sender_telegram_user_id=sender_id or None,
                direction=direction,
                content_type=MessageContentType.TEXT,
                text_content=self._clean_optional_text(str(item.get("text") or "")),
                media_type=None,
                media_url=None,
                media_key=None,
                emoji=None,
                status=MessageSendStatus.SENT,
                telegram_message_id=telegram_message_id,
                reply_to_telegram_message_id=(
                    int(item.get("reply_to_message_id"))
                    if item.get("reply_to_message_id") is not None
                    else None
                ),
                forward_from_telegram_user_id=(
                    int(item.get("forward_from_user_id"))
                    if item.get("forward_from_user_id") is not None
                    else None
                ),
                source_message_id=None,
                task_execution_log_id=None,
                error_message=None,
                sent_at=message_at if direction == MessageDirection.OUT else None,
                message_at=message_at,
            )
            await self._message_repository.Save(message_record)

        await self._session.commit()
        return messages

    # ========== Messages 路径（PR #5 保留） ==========

    async def _build_message_content(
        self,
        account_id: int,
        content_type: MessageContentType | str | None,
        content: str,
        text_content: str | None,
        media_type: MessageMediaType | str | None,
        media_url: str | None,
        media_key: str | None,
        emoji: str | None,
        caption: str | None,
        media_items: list[dict[str, Any]] | None,
        message_content_id: int | None,
    ) -> tuple[MessageContent, list[MessageContentMedia]]:
        if message_content_id is not None:
            message_content = await self._message_content_repository.FindById(message_content_id)
            if message_content is None:
                raise ValueError("消息内容不存在")
            content_media_items = await self._message_content_media_repository.FindAllByMessageContentIdOrderBySortOrderAsc(
                message_content_id=int(message_content.id)
            )
            return message_content, content_media_items

        normalized_content_type = self._normalize_content_type(content_type)
        normalized_text_content = self._clean_optional_text(text_content) or self._clean_optional_text(content)
        normalized_media_type = self._normalize_media_type(media_type)
        normalized_media_url = self._clean_optional_text(media_url)
        normalized_media_key = self._clean_optional_text(media_key)
        normalized_emoji = self._clean_optional_text(emoji)
        normalized_caption = self._clean_optional_text(caption)
        message_content = MessageContent(
            account_id=account_id,
            content_type=normalized_content_type,
            text_content=normalized_text_content,
            media_type=normalized_media_type,
            media_url=normalized_media_url,
            media_key=normalized_media_key,
            emoji=normalized_emoji,
            caption=normalized_caption,
            extra_json="{}",
            is_active=True,
        )
        await self._message_content_repository.Save(message_content)

        normalized_media_items: list[dict[str, Any]] = []
        if media_items:
            for index, item in enumerate(media_items):
                if not isinstance(item, dict):
                    continue
                normalized_media_items.append(
                    {
                        "media_type": self._normalize_media_type(item.get("media_type")) or MessageMediaType.FILE,
                        "media_url": self._clean_optional_text(item.get("media_url")),
                        "media_key": self._clean_optional_text(item.get("media_key")),
                        "caption": self._clean_optional_text(item.get("caption")),
                        "sort_order": int(item.get("sort_order") or index),
                    }
                )

        if (normalized_media_url or normalized_media_key) and not normalized_media_items:
            normalized_media_items.append(
                {
                    "media_type": normalized_media_type or MessageMediaType.FILE,
                    "media_url": normalized_media_url,
                    "media_key": normalized_media_key,
                    "caption": normalized_caption,
                    "sort_order": 0,
                }
            )

        content_media_items: list[MessageContentMedia] = []
        for item in normalized_media_items:
            media_detail = MessageContentMedia(
                message_content_id=int(message_content.id),
                media_type=item["media_type"],
                media_url=item["media_url"],
                media_key=item["media_key"],
                caption=item["caption"],
                sort_order=item["sort_order"],
            )
            await self._message_content_media_repository.Save(media_detail)
            content_media_items.append(media_detail)

        return message_content, content_media_items

    async def _create_send_attempt(self, telegram_message_id: int, attempt_no: int) -> TelegramMessageSendAttempt:
        attempt = TelegramMessageSendAttempt(
            telegram_message_id=telegram_message_id,
            attempt_no=attempt_no,
            status=MessageAttemptStatus.SENDING,
            telegram_message_id_value=None,
            error_message=None,
            started_at=datetime.utcnow(),
            finished_at=None,
            duration_ms=0,
        )
        await self._message_send_attempt_repository.Save(attempt)
        return attempt

    async def ListSendRecords(self, account_id: int, limit: int = 50) -> list[dict[str, Any]]:
        records = await self._message_repository.FindAllByAccountIdAndDirectionOrderByIdDesc(
            account_id=account_id,
            direction=MessageDirection.OUT,
            limit=limit,
        )
        return [
            {
                "id": int(record.id),
                "account_id": int(record.account_id),
                "message_content_id": record.message_content_id,
                "source_type": str(record.source_type),
                "conversation_id": record.conversation_id,
                "conversation_peer": record.conversation_peer,
                "content_type": str(record.content_type),
                "text_content": record.text_content,
                "media_type": str(record.media_type) if record.media_type else None,
                "media_url": record.media_url,
                "media_key": record.media_key,
                "emoji": record.emoji,
                "status": str(record.status),
                "telegram_message_id": record.telegram_message_id,
                "error_message": record.error_message,
                "sent_at": record.sent_at.isoformat() if record.sent_at else None,
                "message_at": record.message_at.isoformat() if record.message_at else None,
            }
            for record in records
        ]

    async def SendMessage(
        self,
        account_id: int,
        target_identifier: str,
        content: str = "",
        content_type: MessageContentType | str = MessageContentType.TEXT,
        text_content: str | None = None,
        media_type: MessageMediaType | str | None = None,
        media_url: str | None = None,
        media_key: str | None = None,
        emoji: str | None = None,
        caption: str | None = None,
        media_items: list[dict[str, Any]] | None = None,
        source_type: MessageSourceType | str = MessageSourceType.MANUAL,
        message_content_id: int | None = None,
        task_execution_log_id: int | None = None,
    ) -> dict[str, Any]:
        account = await self._get_account_or_raise(account_id)
        conversation_id: int | None = int(target_identifier) if target_identifier.isdigit() else None
        message_content, content_media_items = await self._build_message_content(
            account_id=int(account.id),
            content_type=content_type,
            content=content,
            text_content=text_content,
            media_type=media_type,
            media_url=media_url,
            media_key=media_key,
            emoji=emoji,
            caption=caption,
            media_items=media_items,
            message_content_id=message_content_id,
        )

        send_text = message_content.text_content or content or message_content.caption or message_content.emoji or ""

        message_record = TelegramMessage(
            account_id=int(account.id),
            message_content_id=int(message_content.id),
            source_type=self._normalize_source_type(source_type),
            conversation_id=conversation_id,
            conversation_peer=target_identifier,
            grouped_id=None,
            group_index=0,
            peer_type=TelegramPeerType.UNKNOWN,
            peer_id=None,
            sender_telegram_user_id=int(account.telegram_user_id) if account.telegram_user_id else None,
            direction=MessageDirection.OUT,
            content_type=message_content.content_type,
            text_content=message_content.text_content,
            media_type=message_content.media_type,
            media_url=message_content.media_url,
            media_key=message_content.media_key,
            emoji=message_content.emoji,
            status=MessageSendStatus.PENDING,
            telegram_message_id=None,
            reply_to_telegram_message_id=None,
            forward_from_telegram_user_id=None,
            source_message_id=None,
            task_execution_log_id=task_execution_log_id,
            error_message=None,
            sent_at=None,
            message_at=datetime.utcnow(),
        )
        await self._message_repository.Save(message_record)
        await self._session.flush()

        send_media_items = list(content_media_items)
        if not send_media_items and (message_content.media_url or message_content.media_key):
            send_media_items = [
                MessageContentMedia(
                    message_content_id=int(message_content.id),
                    media_type=message_content.media_type or MessageMediaType.FILE,
                    media_url=message_content.media_url,
                    media_key=message_content.media_key,
                    caption=message_content.caption,
                    sort_order=0,
                )
            ]

        sent_ids: list[int] = []
        failure_error: str | None = None

        if send_media_items:
            for index, media_item in enumerate(send_media_items, start=1):
                attempt = await self._create_send_attempt(telegram_message_id=int(message_record.id), attempt_no=index)
                try:
                    sent_result = await self._telegram_adapter.SendMessage(
                        account_id=int(account.id),
                        session_string=account.session_string or "",
                        target_identifier=target_identifier,
                        content=send_text,
                        media_url=media_item.media_url or media_item.media_key,
                        media_caption=media_item.caption or message_content.caption,
                    )
                    sent_id = int(sent_result.get("message_id") or 0)
                    if sent_id > 0:
                        sent_ids.append(sent_id)

                    if sent_result.get("grouped_id") is not None:
                        message_record.grouped_id = int(sent_result.get("grouped_id"))
                    message_record.peer_type = self._normalize_peer_type(sent_result.get("peer_type"))
                    message_record.peer_id = (
                        int(sent_result.get("peer_id"))
                        if sent_result.get("peer_id") is not None
                        else message_record.peer_id
                    )
                    message_record.reply_to_telegram_message_id = (
                        int(sent_result.get("reply_to_message_id"))
                        if sent_result.get("reply_to_message_id") is not None
                        else message_record.reply_to_telegram_message_id
                    )
                    message_record.sender_telegram_user_id = (
                        int(sent_result.get("sender_id"))
                        if sent_result.get("sender_id") is not None
                        else message_record.sender_telegram_user_id
                    )

                    message_media = TelegramMessageMedia(
                        telegram_message_id=int(message_record.id),
                        grouped_id=message_record.grouped_id,
                        media_type=media_item.media_type,
                        media_url=media_item.media_url,
                        media_key=media_item.media_key,
                        caption=media_item.caption,
                        telegram_media_id=str(sent_id) if sent_id > 0 else "",
                        sort_order=media_item.sort_order,
                    )
                    await self._message_media_repository.Save(message_media)

                    attempt.status = MessageAttemptStatus.SENT
                    attempt.telegram_message_id_value = sent_id if sent_id > 0 else None
                    attempt.error_message = None
                except Exception as exc:
                    failure_error = str(exc)
                    attempt.status = MessageAttemptStatus.FAILED
                    attempt.telegram_message_id_value = None
                    attempt.error_message = failure_error

                attempt.finished_at = datetime.utcnow()
                attempt.duration_ms = int((attempt.finished_at - (attempt.started_at or attempt.finished_at)).total_seconds() * 1000)
                if failure_error:
                    break
        else:
            attempt = await self._create_send_attempt(telegram_message_id=int(message_record.id), attempt_no=1)
            try:
                sent_result = await self._telegram_adapter.SendMessage(
                    account_id=int(account.id),
                    session_string=account.session_string or "",
                    target_identifier=target_identifier,
                    content=send_text,
                )
                sent_id = int(sent_result.get("message_id") or 0)
                if sent_id > 0:
                    sent_ids.append(sent_id)
                if sent_result.get("grouped_id") is not None:
                    message_record.grouped_id = int(sent_result.get("grouped_id"))
                message_record.peer_type = self._normalize_peer_type(sent_result.get("peer_type"))
                message_record.peer_id = (
                    int(sent_result.get("peer_id"))
                    if sent_result.get("peer_id") is not None
                    else message_record.peer_id
                )
                message_record.reply_to_telegram_message_id = (
                    int(sent_result.get("reply_to_message_id"))
                    if sent_result.get("reply_to_message_id") is not None
                    else message_record.reply_to_telegram_message_id
                )
                message_record.sender_telegram_user_id = (
                    int(sent_result.get("sender_id"))
                    if sent_result.get("sender_id") is not None
                    else message_record.sender_telegram_user_id
                )
                attempt.status = MessageAttemptStatus.SENT
                attempt.telegram_message_id_value = sent_id if sent_id > 0 else None
                attempt.error_message = None
            except Exception as exc:
                failure_error = str(exc)
                attempt.status = MessageAttemptStatus.FAILED
                attempt.telegram_message_id_value = None
                attempt.error_message = failure_error

            attempt.finished_at = datetime.utcnow()
            attempt.duration_ms = int((attempt.finished_at - (attempt.started_at or attempt.finished_at)).total_seconds() * 1000)

        if failure_error:
            message_record.status = MessageSendStatus.FAILED
            message_record.error_message = failure_error
            message_record.telegram_message_id = sent_ids[0] if sent_ids else None
            message_record.sent_at = datetime.utcnow() if sent_ids else None
        else:
            message_record.status = MessageSendStatus.SENT
            message_record.error_message = None
            message_record.telegram_message_id = sent_ids[0] if sent_ids else None
            message_record.sent_at = datetime.utcnow()

        message_record.message_at = datetime.utcnow()
        await self._session.commit()

        return {
            "account_id": int(account.id),
            "target_identifier": target_identifier,
            "content": send_text,
            "content_type": str(message_content.content_type),
            "message_content_id": int(message_content.id),
            "send_log_id": int(message_record.id),
            "source_type": str(message_record.source_type),
            "status": str(message_record.status),
            "telegram_message_id": message_record.telegram_message_id,
            "error": failure_error,
        }
