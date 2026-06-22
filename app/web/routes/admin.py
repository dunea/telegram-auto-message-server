import logging
import uuid
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select, func, case, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.user import User
from app.models.account import TelegramAccount, ProxyInfo
from app.models.task import ScheduledMessageTask
from app.models.message import TelegramMessage
from app.web import templates
from app.web.dependencies import get_current_user_from_cookie, get_current_admin_from_cookie

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/web", tags=["web-admin"])


@router.get("/select-role", response_class=HTMLResponse)
async def select_role_page(
    request: Request,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: AsyncSession = Depends(get_db_session)
):
    """管理员登录后的角色选择页面。"""
    user = await db_session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=303, headers={"Location": "/web/login"})
    if not user.is_admin:
        # 非管理员直接进入前台
        return RedirectResponse(url="/web/dashboard", status_code=303)
        
    return templates.TemplateResponse(request, "admin/select_role.html", {
        "user": user
    })


# 以下所有路由均需要管理员权限
@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    admin: User = Depends(get_current_admin_from_cookie),
    db_session: AsyncSession = Depends(get_db_session)
):
    """管理员仪表盘。"""
    # 统计各项系统全局数据
    total_users = await db_session.scalar(select(func.count(User.id)))
    active_users = await db_session.scalar(select(func.count(User.id)).where(User.is_active == True))
    
    total_accounts = await db_session.scalar(select(func.count(TelegramAccount.id)))
    online_accounts = await db_session.scalar(select(func.count(TelegramAccount.id)).where(TelegramAccount.is_online == True))
    
    total_proxies = await db_session.scalar(select(func.count(ProxyInfo.id)))
    active_proxies = await db_session.scalar(select(func.count(ProxyInfo.id)).where(ProxyInfo.is_active == True))
    
    total_tasks = await db_session.scalar(select(func.count(ScheduledMessageTask.id)))
    
    # 统计今日发送的消息总数
    from datetime import datetime, time, timezone
    utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
    today_start = datetime.combine(utc_now.date(), time.min)
    today_messages = await db_session.scalar(
        select(func.count(TelegramMessage.id)).where(TelegramMessage.created_at >= today_start)
    )

    return templates.TemplateResponse(request, "admin/dashboard.html", {
        "admin": admin,
        "total_users": total_users or 0,
        "active_users": active_users or 0,
        "total_accounts": total_accounts or 0,
        "online_accounts": online_accounts or 0,
        "total_proxies": total_proxies or 0,
        "active_proxies": active_proxies or 0,
        "total_tasks": total_tasks or 0,
        "today_messages": today_messages or 0,
    })


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    admin: User = Depends(get_current_admin_from_cookie),
    db_session: AsyncSession = Depends(get_db_session)
):
    """用户管理列表页。"""
    users = (await db_session.scalars(select(User).order_by(User.id.desc()))).all()
    return templates.TemplateResponse(request, "admin/users.html", {
        "admin": admin,
        "users": users
    })


@router.post("/admin/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    admin: User = Depends(get_current_admin_from_cookie),
    db_session: AsyncSession = Depends(get_db_session)
):
    """启用/禁用用户（软删除）。"""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能禁用自己")
        
    user = await db_session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
        
    user.is_active = not user.is_active
    await db_session.commit()
    
    label = "● 正常" if user.is_active else "○ 已禁用"
    color_class = "text-green-600 font-bold" if user.is_active else "text-red-500 font-bold"
    
    return HTMLResponse(f"""
        <button hx-post="/web/admin/users/{user_id}/toggle-active"
                hx-target="this"
                hx-swap="outerHTML"
                class="inline-flex items-center px-2.5 py-1.5 border border-gray-300 shadow-sm text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50">
            <span class="{color_class}">{label}</span>
        </button>
    """)


@router.post("/admin/users/{user_id}/toggle-admin")
async def toggle_user_admin(
    user_id: int,
    admin: User = Depends(get_current_admin_from_cookie),
    db_session: AsyncSession = Depends(get_db_session)
):
    """设为/取消管理员。"""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能修改自己的管理员权限")
        
    user = await db_session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
        
    user.is_admin = not user.is_admin
    await db_session.commit()
    
    label = "管理员" if user.is_admin else "普通用户"
    color_class = "text-indigo-600 font-bold" if user.is_admin else "text-gray-500"
    
    return HTMLResponse(f"""
        <button hx-post="/web/admin/users/{user_id}/toggle-admin"
                hx-target="this"
                hx-swap="outerHTML"
                class="inline-flex items-center px-2.5 py-1.5 border border-gray-300 shadow-sm text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50">
            <span class="{color_class}">{label}</span>
        </button>
    """)


@router.post("/admin/users/{user_id}/reset-api-key")
async def reset_user_api_key(
    user_id: int,
    admin: User = Depends(get_current_admin_from_cookie),
    db_session: AsyncSession = Depends(get_db_session)
):
    """重置 API key。"""
    user = await db_session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
        
    user.api_key = uuid.uuid4().hex
    await db_session.commit()
    
    masked_key = f"{user.api_key[:8]}••••••••••••••••"
    return HTMLResponse(f"""
        <div id="api-key-{user_id}" class="flex items-center gap-1.5 justify-center">
            <span class="api-key-text font-mono text-xs text-slate-600 bg-slate-100 px-2 py-1 rounded select-all cursor-pointer" 
                  onclick="var self=this; if(self.dataset.masked==='1'){{ self.textContent=self.dataset.full; self.dataset.masked='0'; }} else {{ self.textContent=self.dataset.masked_val; self.dataset.masked='1'; }}"
                  data-masked="1"
                  data-full="{user.api_key}"
                  data-masked_val="{masked_key}"
                  title="点击显示/隐藏">
                {masked_key}
            </span>
            <button hx-post="/web/admin/users/{user_id}/reset-api-key"
                    hx-target="#api-key-{user_id}"
                    hx-swap="outerHTML"
                    hx-confirm="确定要重置此用户 ({user.email}) 的 API Key 吗？"
                    class="text-indigo-600 hover:text-indigo-900 text-xs font-semibold">
                重置
            </button>
        </div>
    """)


@router.get("/admin/proxies", response_class=HTMLResponse)
async def admin_proxies(
    request: Request,
    admin: User = Depends(get_current_admin_from_cookie),
    db_session: AsyncSession = Depends(get_db_session)
):
    """代理 IP 列表页。"""
    stmt = (
        select(
            ProxyInfo,
            func.count(TelegramAccount.id).label("account_count")
        )
        .outerjoin(TelegramAccount, (ProxyInfo.id == TelegramAccount.proxy_id) & (TelegramAccount.is_active == True))
        .group_by(ProxyInfo.id)
        .order_by(ProxyInfo.id.desc())
    )
    results = (await db_session.execute(stmt)).all()
    
    proxies_data = []
    for row in results:
        p = row[0]
        count = row[1]
        proxies_data.append({
            "id": p.id,
            "proxy_host": p.proxy_host,
            "proxy_port": p.proxy_port,
            "username": p.username,
            "password": p.password,
            "proxy_type": p.proxy_type,
            "is_active": p.is_active,
            "account_count": count
        })
        
    return templates.TemplateResponse(request, "admin/proxies.html", {
        "admin": admin,
        "proxies": proxies_data
    })


@router.post("/admin/proxies/add")
async def add_proxy(
    request: Request,
    host: str = Form(...),
    port: int = Form(...),
    username: str = Form(None),
    password: str = Form(None),
    proxy_type: str = Form("socks5"),
    admin: User = Depends(get_current_admin_from_cookie),
    db_session: AsyncSession = Depends(get_db_session)
):
    """添加单个代理。"""
    username = username.strip() if username else None
    password = password.strip() if password else None
    
    proxy = ProxyInfo(
        proxy_host=host.strip(),
        proxy_port=port,
        username=username,
        password=password,
        proxy_type=proxy_type,
        is_active=True
    )
    db_session.add(proxy)
    await db_session.commit()
    
    return RedirectResponse("/web/admin/proxies", status_code=303)


def _parse_proxy_line(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None
        
    # 尝试解析 protocol://user:pass@host:port
    if "://" in line:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(line)
            proxy_type = parsed.scheme.lower()
            if proxy_type not in ("socks5", "socks4", "http"):
                proxy_type = "socks5"
            host = parsed.hostname
            port = parsed.port
            username = parsed.username
            password = parsed.password
            if host and port:
                return {
                    "proxy_host": host,
                    "proxy_port": int(port),
                    "username": username,
                    "password": password,
                    "proxy_type": proxy_type
                }
        except Exception as exc:
            logger.debug(f"Failed parsing proxy with schema parser: {exc}", exc_info=True)
            
    # 支持 IPv6: 例如 [2001:db8::1]:1080 或 [2001:db8::1]:1080:user:pass
    if line.startswith("["):
        idx_close = line.find("]")
        if idx_close != -1:
            host = line[1:idx_close]
            rest = line[idx_close+1:]
            if rest.startswith(":"):
                parts = rest[1:].split(":")
                if len(parts) >= 1:
                    try:
                        port = int(parts[0].strip())
                        username = parts[1].strip() if len(parts) >= 2 else None
                        password = parts[2].strip() if len(parts) >= 3 else None
                        return {
                            "proxy_host": host,
                            "proxy_port": port,
                            "username": username,
                            "password": password,
                            "proxy_type": "socks5"
                        }
                    except ValueError as exc:
                        logger.debug(f"Failed parsing IPv6 port: {exc}", exc_info=True)
                        return None
        return None

    # 尝试按冒号切分 host:port:user:pass 或 host:port (IPv4 或域名)
    parts = line.split(":")
    if len(parts) >= 2:
        host = parts[0].strip()
        try:
            port = int(parts[1].strip())
        except ValueError as exc:
            logger.debug(f"Failed parsing port from non-IPv6 line: {exc}", exc_info=True)
            return None
        
        username = None
        password = None
        if len(parts) == 4:
            username = parts[2].strip()
            password = parts[3].strip()
            
        return {
            "proxy_host": host,
            "proxy_port": port,
            "username": username,
            "password": password,
            "proxy_type": "socks5"
        }
    return None


@router.post("/admin/proxies/import")
async def import_proxies(
    request: Request,
    text_content: str = Form(...),
    admin: User = Depends(get_current_admin_from_cookie),
    db_session: AsyncSession = Depends(get_db_session)
):
    """批量导入代理。"""
    lines = text_content.strip().splitlines()
    success_count = 0
    
    for line in lines:
        parsed = _parse_proxy_line(line)
        if parsed:
            proxy = ProxyInfo(
                proxy_host=parsed["proxy_host"],
                proxy_port=parsed["proxy_port"],
                username=parsed["username"],
                password=parsed["password"],
                proxy_type=parsed["proxy_type"],
                is_active=True
            )
            db_session.add(proxy)
            success_count += 1
            
    if success_count > 0:
        await db_session.commit()
        
    from urllib.parse import quote
    response = RedirectResponse("/web/admin/proxies", status_code=303)
    response.set_cookie("flash_success", quote(f"成功批量导入 {success_count} 个代理 IP！"), max_age=10)
    return response


@router.post("/admin/proxies/{proxy_id}/toggle-active")
async def toggle_proxy_active(
    proxy_id: int,
    admin: User = Depends(get_current_admin_from_cookie),
    db_session: AsyncSession = Depends(get_db_session)
):
    """启用/禁用代理。"""
    proxy = await db_session.get(ProxyInfo, proxy_id)
    if not proxy:
        raise HTTPException(status_code=404, detail="代理不存在")
        
    proxy.is_active = not proxy.is_active
    await db_session.commit()
    
    label = "● 启用" if proxy.is_active else "○ 禁用"
    color_class = "text-green-600 font-bold" if proxy.is_active else "text-red-500 font-bold"
    
    return HTMLResponse(f"""
        <button hx-post="/web/admin/proxies/{proxy_id}/toggle-active"
                hx-target="this"
                hx-swap="outerHTML"
                class="inline-flex items-center px-2 py-1 border border-gray-300 shadow-sm text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50">
            <span class="{color_class}">{label}</span>
        </button>
    """)


@router.post("/admin/proxies/{proxy_id}/delete")
async def delete_proxy(
    proxy_id: int,
    request: Request,
    admin: User = Depends(get_current_admin_from_cookie),
    db_session: AsyncSession = Depends(get_db_session)
):
    """软删除单个代理。"""
    proxy = await db_session.get(ProxyInfo, proxy_id)
    if not proxy:
        raise HTTPException(status_code=404, detail="代理不存在")
        
    # 软删除
    proxy.is_active = False
    await db_session.commit()
    
    if "HX-Request" in request.headers:
        response = Response()
        response.headers["HX-Redirect"] = "/web/admin/proxies"
        return response
    return RedirectResponse("/web/admin/proxies", status_code=303)


@router.post("/admin/proxies/batch-delete")
async def batch_delete_proxies(
    request: Request,
    admin: User = Depends(get_current_admin_from_cookie),
    db_session: AsyncSession = Depends(get_db_session)
):
    """批量软删除选中的代理。"""
    form_data = await request.form()
    proxy_ids = [int(k.split("-")[1]) for k in form_data.keys() if k.startswith("proxy-")]
    
    if proxy_ids:
        # 执行批量软删除：将 is_active 设为 False
        stmt = update(ProxyInfo).where(ProxyInfo.id.in_(proxy_ids)).values(is_active=False)
        await db_session.execute(stmt)
        await db_session.commit()
        
    from urllib.parse import quote
    response = RedirectResponse("/web/admin/proxies", status_code=303)
    response.set_cookie("flash_success", quote(f"成功批量软删除 {len(proxy_ids)} 个代理 IP。"), max_age=10)
    return response
