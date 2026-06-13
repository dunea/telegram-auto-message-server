"""服务运行状态 Web 路由模块。

提供本项目及其所连外部服务（数据库、号池实例集群、定时任务调度器）运行状态的监控界面。
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, case, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_task_scheduler
from app.config import get_settings
from app.web import templates
from app.web.dependencies import get_current_user_from_cookie
from app.models.account import TelegramAccount, ProxyInfo, InstanceHeartbeat

router = APIRouter(prefix="/web", tags=["web-status"])


async def fetch_system_status(db_session: AsyncSession, scheduler) -> dict:
    """获取所有系统状态的汇总数据。"""
    settings = get_settings()
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. 检查数据库状态
    db_ok = True
    db_error = None
    try:
        await db_session.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_error = str(e)

    # 2. 统计账号、代理以及消息成功率
    accounts_stat = {"total": 0, "active": 0, "online": 0}
    proxies_stat = {"total": 0, "active": 0}
    messages_stat = {"total_24h": 0, "sent_24h": 0, "success_rate_24h": 100.0}

    if db_ok:
        try:
            acc_stmt = select(
                func.count(TelegramAccount.id),
                func.sum(case((TelegramAccount.is_active == True, 1), else_=0)),
                func.sum(case((TelegramAccount.is_online == True, 1), else_=0)),
            )
            acc_res = (await db_session.execute(acc_stmt)).all()[0]
            accounts_stat = {
                "total": acc_res[0] or 0,
                "active": int(acc_res[1] or 0),
                "online": int(acc_res[2] or 0),
            }

            proxy_stmt = select(
                func.count(ProxyInfo.id),
                func.sum(case((ProxyInfo.is_active == True, 1), else_=0)),
            )
            proxy_res = (await db_session.execute(proxy_stmt)).all()[0]
            proxies_stat = {
                "total": proxy_res[0] or 0,
                "active": int(proxy_res[1] or 0),
            }

            # 统计24小时出站消息
            from app.models.message import TelegramMessage
            last_24h = now_utc - timedelta(hours=24)
            msg_stmt = select(
                func.count(TelegramMessage.id),
                func.sum(case(((TelegramMessage.status == "sent") & (TelegramMessage.direction == "out"), 1), else_=0))
            ).where(TelegramMessage.created_at >= last_24h)
            msg_res = (await db_session.execute(msg_stmt)).all()[0]
            total_msg = msg_res[0] or 0
            sent_msg = int(msg_res[1] or 0)
            success_rate = round((sent_msg / total_msg) * 100, 2) if total_msg > 0 else 100.0
            messages_stat = {
                "total_24h": total_msg,
                "sent_24h": sent_msg,
                "success_rate_24h": success_rate,
            }
        except Exception:
            pass

    # 3. 调度器状态
    scheduler_status = {
        "running": scheduler.running if scheduler else False,
        "job_count": scheduler.job_count if scheduler else 0,
        "job_ids": scheduler.GetJobIds() if scheduler else [],
    }

    # 4. 号池集群实例心跳与分片信息
    active_instances = []
    if db_ok:
        try:
            # 60 秒内有心跳的实例视为活跃
            expiration_time = now_utc - timedelta(seconds=60)
            inst_stmt = select(InstanceHeartbeat).order_by(InstanceHeartbeat.instance_id)
            db_instances = (await db_session.scalars(inst_stmt)).all()

            for inst in db_instances:
                delta_sec = int((now_utc - inst.last_heartbeat).total_seconds())
                is_active = delta_sec < 60
                active_instances.append({
                    "instance_id": inst.instance_id,
                    "last_heartbeat": inst.last_heartbeat,
                    "seconds_ago": max(0, delta_sec),
                    "is_active": is_active
                })
        except Exception:
            pass

    # 过滤出当前真正存活的号池集群实例数
    alive_count = sum(1 for inst in active_instances if inst["is_active"])

    return {
        "service": {
            "name": settings.app_name,
            "mode": settings.mode,
            "utc_time": datetime.now(timezone.utc),
            "local_time": datetime.now(),
        },
        "database": {
            "ok": db_ok,
            "error": db_error,
        },
        "accounts": accounts_stat,
        "proxies": proxies_stat,
        "messages": messages_stat,
        "scheduler": scheduler_status,
        "pool": {
            "instance_id": settings.pool_instance_id,
            "max_concurrent_logins": settings.pool_max_concurrent_logins,
            "total_shards": settings.pool_total_shards,
            "shard_index": settings.pool_shard_index,
            "login_scan_interval_seconds": settings.pool_login_scan_interval_seconds,
            "instances": active_instances,
            "alive_count": alive_count,
        }
    }


@router.get("/status", response_class=HTMLResponse)
async def status_page(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    scheduler=Depends(get_task_scheduler),
):
    """渲染运行状态完整页面。"""
    status_data = await fetch_system_status(db_session, scheduler)
    return templates.TemplateResponse(request, "status/index.html", {
        "status": status_data,
    })


@router.get("/status/partial", response_class=HTMLResponse)
async def status_partial(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    scheduler=Depends(get_task_scheduler),
):
    """HTMX 定时刷新路由：仅渲染状态卡片局部 HTML。"""
    status_data = await fetch_system_status(db_session, scheduler)
    return templates.TemplateResponse(request, "status/_status_cards.html", {
        "status": status_data,
    })
