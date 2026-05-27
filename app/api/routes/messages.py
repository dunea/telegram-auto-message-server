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
        result = await telegram_service.SendMessage(
            account_id=payload.account_id,
            target_identifier=payload.target_identifier,
            content=payload.content,
        )
        return SendMessageResult(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
