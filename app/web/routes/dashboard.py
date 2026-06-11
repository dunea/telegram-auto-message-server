from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.web import templates
from app.web.dependencies import get_current_user_from_cookie
from app.models.account import TelegramAccount
from app.models.task import AutoReplyRule, ScheduledMessageTask
from app.models.message import TelegramMessage

router = APIRouter(prefix="/web", tags=["web-dashboard"])

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: Session = Depends(get_db_session)
):
    # 统计账号
    total_accounts = db_session.scalar(select(func.count(TelegramAccount.id))) or 0
    active_accounts = db_session.scalar(select(func.count(TelegramAccount.id)).where(TelegramAccount.is_active == True)) or 0
    online_accounts = db_session.scalar(select(func.count(TelegramAccount.id)).where(TelegramAccount.is_online == True)) or 0

    # 统计规则
    total_rules = db_session.scalar(select(func.count(AutoReplyRule.id))) or 0
    active_rules = db_session.scalar(select(func.count(AutoReplyRule.id)).where(AutoReplyRule.is_active == True)) or 0

    # 统计定时任务
    total_tasks = db_session.scalar(select(func.count(ScheduledMessageTask.id))) or 0
    active_tasks = db_session.scalar(select(func.count(ScheduledMessageTask.id)).where(ScheduledMessageTask.is_active == True)) or 0

    # 统计24小时出站消息
    last_24h = datetime.utcnow() - timedelta(hours=24)
    out_msg_stmt = select(func.count(TelegramMessage.id)).where(
        TelegramMessage.direction == "out",
        TelegramMessage.created_at >= last_24h
    )
    sent_24h = db_session.scalar(out_msg_stmt.where(TelegramMessage.status == "sent")) or 0
    failed_24h = db_session.scalar(out_msg_stmt.where(TelegramMessage.status == "failed")) or 0
    pending_24h = db_session.scalar(out_msg_stmt.where(TelegramMessage.status == "pending")) or 0
    
    return templates.TemplateResponse("dashboard/index.html", {
        "request": request,
        "user_id": user_id,
        "accounts": {"total": total_accounts, "active": active_accounts, "online": online_accounts},
        "rules": {"total": total_rules, "active": active_rules},
        "tasks": {"total": total_tasks, "active": active_tasks},
        "messages_24h": {"sent": sent_24h, "failed": failed_24h, "pending": pending_24h}
    })
