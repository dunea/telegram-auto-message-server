from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_telegram_service
from app.schema.message import SendMessageRequest, SendMessageResult
from app.service.telegram_service import TelegramService

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/records")
async def list_send_records(
    account_id: int = Query(..., ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> list[dict]:
    return telegram_service.ListSendRecords(account_id=account_id, limit=limit)


@router.post("/send", response_model=SendMessageResult)
async def send_message(
    payload: SendMessageRequest,
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> SendMessageResult:
    try:
        message_content = payload.message_content
        result = await telegram_service.SendMessage(
            account_id=payload.account_id,
            target_identifier=payload.target_identifier,
            content=payload.content,
            content_type=(message_content.content_type if message_content else "text"),
            text_content=(message_content.text_content if message_content else None),
            media_type=(message_content.media_type if message_content else None),
            media_url=(message_content.media_url if message_content else None),
            media_key=(message_content.media_key if message_content else None),
            emoji=(message_content.emoji if message_content else None),
            caption=(message_content.caption if message_content else None),
            media_items=([
                {
                    "media_type": item.media_type,
                    "media_url": item.media_url,
                    "media_key": item.media_key,
                    "caption": item.caption,
                    "sort_order": item.sort_order,
                }
                for item in message_content.media_items
            ] if message_content else None),
            source_type=payload.source_type,
        )
        return SendMessageResult(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
