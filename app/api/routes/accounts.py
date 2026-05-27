from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_telegram_service
from app.schema.account import AccountOnlineRequest, CreateAccountRequest
from app.service.telegram_service import TelegramService

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("")
async def create_telegram_account(
    payload: CreateAccountRequest,
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> dict:
    try:
        return telegram_service.CreateAccount(
            phone_number=payload.phone_number,
            proxy_id=payload.proxy_id,
            session_string=payload.session_string,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
async def list_telegram_accounts(
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> list[dict]:
    return telegram_service.ListManagedAccounts()


@router.post("/{account_id}/online")
async def ensure_telegram_account_online(
    account_id: int,
    payload: AccountOnlineRequest,
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> dict:
    try:
        if payload.session_string:
            telegram_service.UpdateAccountSessionString(account_id=account_id, session_string=payload.session_string)
        return await telegram_service.EnsureAccountOnline(account_id=account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{account_id}/conversations")
async def list_telegram_conversations(
    account_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> list[dict]:
    try:
        return await telegram_service.ListConversations(account_id=account_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{account_id}/messages/{target_identifier}")
async def list_telegram_messages(
    account_id: int,
    target_identifier: str,
    limit: int = Query(default=50, ge=1, le=200),
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> list[dict]:
    try:
        return await telegram_service.ListMessages(
            account_id=account_id,
            target_identifier=target_identifier,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
