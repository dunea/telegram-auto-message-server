import logging
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_telegram_service
from app.models.account import TelegramAccount, ProxyInfo
from app.service.telegram_service import TelegramService
from app.web import templates
from app.web.dependencies import get_current_user_from_cookie

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/web", tags=["web-accounts"])


@router.get("/accounts", response_class=HTMLResponse)
async def list_accounts(
    request: Request,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: AsyncSession = Depends(get_db_session)
):
    accounts = await db_session.scalars(select(TelegramAccount).order_by(TelegramAccount.id))
    proxies = {p.id: p for p in (await db_session.scalars(select(ProxyInfo)))}
    return templates.TemplateResponse(request, "accounts/list.html", {
        "user_id": user_id,
        "accounts": accounts,
        "proxies": proxies
    })


@router.get("/accounts/new", response_class=HTMLResponse)
async def new_account_page(
    request: Request,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: AsyncSession = Depends(get_db_session)
):
    proxies = await db_session.scalars(select(ProxyInfo).where(ProxyInfo.is_active == True))
    return templates.TemplateResponse(request, "accounts/login_flow.html", {
        "user_id": user_id,
        "proxies": proxies
    })


@router.post("/accounts/login/phone/request-code")
async def request_phone_code(
    phone_number: str = Form(...),
    proxy_id: str = Form(""),
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    pid = int(proxy_id) if proxy_id and proxy_id.strip() else None
    try:
        res = await telegram_service.RequestPhoneLoginCode(phone_number, proxy_id=pid)
        account_id = res["account_id"]
        phone_code_hash = res["phone_code_hash"]
        return HTMLResponse(f"""
            <form hx-post="/web/accounts/{account_id}/login/phone/verify-code" hx-target="#login-flow-container" hx-swap="innerHTML" class="space-y-6">
                <input type="hidden" name="phone_code_hash" value="{phone_code_hash}">
                <div class="bg-blue-50 border-l-4 border-blue-400 p-4 mb-4">
                    <p class="text-sm text-blue-700">验证码已发送至 {phone_number}</p>
                </div>
                <div>
                    <label for="code" class="block text-sm font-medium text-gray-700">请输入验证码</label>
                    <input type="text" name="code" id="code" required placeholder="12345"
                           class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                </div>
                <div>
                    <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700">
                        验证验证码
                    </button>
                </div>
            </form>
        """)
    except Exception as e:
        logger.exception("Failed to request code")
        return HTMLResponse(f"""
            <div class="bg-red-50 border-l-4 border-red-400 p-4 mb-4">
                <p class="text-sm text-red-700">错误: {str(e)}</p>
            </div>
            <button onclick="window.location.reload()" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gray-600 hover:bg-gray-700">
                重新开始
            </button>
        """)


@router.post("/accounts/{account_id}/login/phone/verify-code")
async def verify_phone_code(
    account_id: int,
    phone_code_hash: str = Form(...),
    code: str = Form(...),
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    try:
        res = await telegram_service.VerifyPhoneLoginCode(account_id, phone_code_hash, code)
        if res.get("next_step") == "verify_password":
            return HTMLResponse(f"""
                <form hx-post="/web/accounts/{account_id}/login/phone/verify-password" hx-target="#login-flow-container" hx-swap="innerHTML" class="space-y-6">
                    <div class="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-4">
                        <p class="text-sm text-yellow-700">该账号启用了两步验证，请输入二级密码。</p>
                    </div>
                    <div>
                        <label for="password" class="block text-sm font-medium text-gray-700">二级密码</label>
                        <input type="password" name="password" id="password" required
                               class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                    </div>
                    <div>
                        <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700">
                            确认登录
                        </button>
                    </div>
                </form>
            """)
        
        response = Response()
        response.headers["HX-Redirect"] = "/web/accounts"
        return response
    except Exception as e:
        logger.exception("Failed to verify code")
        return HTMLResponse(f"""
            <div class="bg-red-50 border-l-4 border-red-400 p-4 mb-4">
                <p class="text-sm text-red-700">错误: {str(e)}</p>
            </div>
            <button onclick="window.location.reload()" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gray-600 hover:bg-gray-700">
                重新开始
            </button>
        """)


@router.post("/accounts/{account_id}/login/phone/verify-password")
async def verify_two_factor(
    account_id: int,
    password: str = Form(...),
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    try:
        await telegram_service.VerifyTwoFactorPassword(account_id, password)
        response = Response()
        response.headers["HX-Redirect"] = "/web/accounts"
        return response
    except Exception as e:
        logger.exception("Failed to verify 2FA password")
        return HTMLResponse(f"""
            <div class="bg-red-50 border-l-4 border-red-400 p-4 mb-4">
                <p class="text-sm text-red-700">错误: {str(e)}</p>
            </div>
            <button onclick="window.location.reload()" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gray-600 hover:bg-gray-700">
                重新开始
            </button>
        """)


@router.post("/accounts/login/session")
async def login_with_session(
    phone_number: str = Form(...),
    session_string: str = Form(...),
    proxy_id: str = Form(""),
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    pid = int(proxy_id) if proxy_id and proxy_id.strip() else None
    try:
        await telegram_service.CreateAccountWithSessionLogin(phone_number, session_string, proxy_id=pid)
        response = Response()
        response.headers["HX-Redirect"] = "/web/accounts"
        return response
    except Exception as e:
        logger.exception("Failed to login with session")
        return HTMLResponse(f"""
            <div class="bg-red-50 border-l-4 border-red-400 p-4 mb-4">
                <p class="text-sm text-red-700">导入失败: {str(e)}</p>
            </div>
            <button onclick="window.location.reload()" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gray-600 hover:bg-gray-700">
                重新开始
            </button>
        """)


@router.get("/accounts/{account_id}", response_class=HTMLResponse)
async def get_account_detail(
    request: Request,
    account_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    account = await db_session.get(TelegramAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    proxy = await db_session.get(ProxyInfo, account.proxy_id) if account.proxy_id else None
    
    conversations = []
    error_msg = None
    if account.is_online:
        try:
            conversations = await telegram_service.ListConversations(account_id)
        except Exception as e:
            logger.exception("Failed to load conversations")
            error_msg = f"会话加载失败: {str(e)}"
            
    return templates.TemplateResponse(request, "accounts/detail.html", {
        "user_id": user_id,
        "account": account,
        "proxy": proxy,
        "conversations": conversations,
        "error_msg": error_msg
    })


@router.post("/accounts/{account_id}/toggle-active")
async def toggle_active(
    account_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    user_id: int = Depends(get_current_user_from_cookie),
):
    account = await db_session.get(TelegramAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    account.is_active = not account.is_active
    await db_session.commit()

    label = "● 启用中" if account.is_active else "○ 已禁用"
    color_class = "text-green-600 font-bold" if account.is_active else "text-red-500 font-bold"
    
    return HTMLResponse(f"""
        <button id="status-badge-{account_id}"
                hx-post="/web/accounts/{account_id}/toggle-active"
                hx-target="#status-badge-{account_id}"
                hx-swap="outerHTML"
                class="inline-flex items-center px-3 py-1.5 border border-gray-300 shadow-sm text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50">
            <span class="{color_class}">{label}</span>
        </button>
    """)


@router.post("/accounts/{account_id}/delete")
async def delete_account(
    account_id: int,
    request: Request,
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    try:
        await telegram_service.SoftDeleteAccount(account_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    if "HX-Request" in request.headers:
        response = Response()
        response.headers["HX-Redirect"] = "/web/accounts"
        return response
    return RedirectResponse("/web/accounts", status_code=303)


@router.post("/accounts/{account_id}/online")
async def online_account(
    account_id: int,
    request: Request,
    telegram_service: TelegramService = Depends(get_telegram_service),
    user_id: int = Depends(get_current_user_from_cookie),
):
    try:
        await telegram_service.EnsureAccountOnline(account_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    if "HX-Request" in request.headers:
        response = Response()
        response.headers["HX-Redirect"] = f"/web/accounts/{account_id}"
        return response
    return RedirectResponse(f"/web/accounts/{account_id}", status_code=303)
