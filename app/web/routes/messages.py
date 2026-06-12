import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.account import TelegramAccount
from app.models.message import TelegramMessage
from app.web import templates
from app.web.dependencies import get_current_user_from_cookie

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/web", tags=["web-messages"])


@router.get("/messages", response_class=HTMLResponse)
async def list_messages(
    request: Request,
    account_id: int | None = None,
    direction: str | None = None,
    limit: int = 100,
    offset: int = 0,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: AsyncSession = Depends(get_db_session),
):
    # 查询所有托管账号，用于在顶部下拉筛选
    accounts = (await db_session.scalars(
        select(TelegramAccount).order_by(TelegramAccount.id)
    )).all()
    accounts_map = {acc.id: acc for acc in accounts}

    # 构建消息查询语句
    stmt = select(TelegramMessage).order_by(TelegramMessage.id.desc())

    # 按托管账号过滤
    if account_id and account_id > 0:
        stmt = stmt.where(TelegramMessage.account_id == account_id)

    # 按消息方向过滤
    if direction:
        stmt = stmt.where(TelegramMessage.direction == direction)

    # 分页限制
    stmt = stmt.limit(limit).offset(offset)
    messages = (await db_session.scalars(stmt)).all()

    return templates.TemplateResponse(
        request,
        "messages/list.html",
        {
            "user_id": user_id,
            "messages": messages,
            "accounts": accounts,
            "accounts_map": accounts_map,
            "selected_account_id": account_id,
            "selected_direction": direction,
        },
    )

