from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

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
    db_session: AsyncSession = Depends(get_db_session),
):
    # 说明（PR #9 阶段）：
    # 1. db_session 是 SQLAlchemy 同步 Session，async def 路由 + sync session 是
    #    FastAPI 内部 anyio 线程池派发的标准模式（PR #4 已采用），无阻塞问题；
    # 2. PR #11 收尾阶段改用 get_db_session 注入 AsyncSession 时，
    #    本文件所有 db_session.scalar/scalars/get 改 await db_session.xxx 即可。
    # 统计账号
    acc_stmt = select(
        func.count(TelegramAccount.id),
        func.sum(case((TelegramAccount.is_active == True, 1), else_=0)),
        func.sum(case((TelegramAccount.is_online == True, 1), else_=0)),
    )
    acc_res = (await db_session.execute(acc_stmt)).all()[0]
    total_accounts = acc_res[0] or 0
    active_accounts = int(acc_res[1] or 0)
    online_accounts = int(acc_res[2] or 0)

    # 统计规则
    rule_stmt = select(
        func.count(AutoReplyRule.id),
        func.sum(case((AutoReplyRule.is_active == True, 1), else_=0)),
    )
    rule_res = (await db_session.execute(rule_stmt)).all()[0]
    total_rules = rule_res[0] or 0
    active_rules = int(rule_res[1] or 0)

    # 统计定时任务
    task_stmt = select(
        func.count(ScheduledMessageTask.id),
        func.sum(case((ScheduledMessageTask.is_active == True, 1), else_=0)),
    )
    task_res = (await db_session.execute(task_stmt)).all()[0]
    total_tasks = task_res[0] or 0
    active_tasks = int(task_res[1] or 0)

    # 统计24小时出站消息
    last_24h = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    msg_stmt = select(
        func.sum(case(((TelegramMessage.status == "sent") & (TelegramMessage.direction == "out") & (TelegramMessage.created_at >= last_24h), 1), else_=0)),
        func.sum(case(((TelegramMessage.status == "failed") & (TelegramMessage.direction == "out") & (TelegramMessage.created_at >= last_24h), 1), else_=0)),
        func.sum(case(((TelegramMessage.status == "pending") & (TelegramMessage.direction == "out") & (TelegramMessage.created_at >= last_24h), 1), else_=0)),
    )
    msg_res = (await db_session.execute(msg_stmt)).all()[0]
    sent_24h = int(msg_res[0] or 0)
    failed_24h = int(msg_res[1] or 0)
    pending_24h = int(msg_res[2] or 0)

    return templates.TemplateResponse(request, "dashboard/index.html", {
        "user_id": user_id,
        "accounts": {"total": total_accounts, "active": active_accounts, "online": online_accounts},
        "rules": {"total": total_rules, "active": active_rules},
        "tasks": {"total": total_tasks, "active": active_tasks},
        "messages_24h": {"sent": sent_24h, "failed": failed_24h, "pending": pending_24h},
    })
