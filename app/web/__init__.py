import os

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates


# 前端展示用的站点品牌信息（与 settings.app_name 解耦，不影响 OpenAPI 标题）。
SITE_NAME = "Telegram 自动消息"
SITE_SUBTITLE = "多账号托管 · 智能自动回复 · 定时群发"
SITE_SOCIAL_TAGLINE = "多账号托管 / 自动回复 / 定时群发"
SITE_DESCRIPTION = (
    "Telegram 自动消息是一款面向运营者与开发者的 Telegram 营销自动化平台，"
    "支持多账号批量托管、关键词自动回复、Cron 定时群发与媒体文件管理。"
    "基于 FastAPI + Telethon 构建，账号安全可控、消息稳定触达。"
)
SITE_KEYWORDS = (
    "Telegram 自动消息, Telegram 群发, Telegram 营销, Telegram 自动回复, "
    "Telegram 定时消息, Telegram 机器人, Telegram 群管理, 多账号托管, "
    "Telethon, FastAPI"
)

web_router = APIRouter(prefix="/web")
templates = Jinja2Templates(directory="templates")
templates.env.globals.update({
    "site_name": SITE_NAME,
    "site_subtitle": SITE_SUBTITLE,
    "site_social_tagline": SITE_SOCIAL_TAGLINE,
    "site_description": SITE_DESCRIPTION,
    "site_keywords": SITE_KEYWORDS,
})
# 集中注册所有模板共享的 filters，避免各路由文件重复定义 templates 实例。
templates.env.filters["basename"] = lambda path: os.path.basename(path) if path else ""

# 自动解析 Cookie 并注入模板上下文的包装器
_original_template_response = templates.TemplateResponse

def custom_template_response(request, name: str, context: dict = None, *args, **kwargs):
    if context is None:
        context = {}
    if "request" not in context:
        context["request"] = request

    # 检测并读取 flash_error 闪存 Cookie
    flash_error = request.cookies.get("flash_error")
    if flash_error:
        try:
            import urllib.parse
            context["error"] = urllib.parse.unquote(flash_error)
        except Exception:
            pass

    # 检测并读取 flash_success 闪存 Cookie
    flash_success = request.cookies.get("flash_success")
    if flash_success:
        try:
            import urllib.parse
            context["success_msg"] = urllib.parse.unquote(flash_success)
        except Exception:
            pass

    token = request.cookies.get("web_token")
    if token:
        try:
            import jwt
            from app.config import get_settings
            settings = get_settings()
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            email = payload.get("email")
            user_id = payload.get("sub")
            if email and user_id:
                class SimpleUser:
                    def __init__(self, uid, email):
                        self.id = uid
                        self.email = email
                context["current_user"] = SimpleUser(int(user_id), email)
                context["user_id"] = int(user_id)
        except Exception:
            pass
            
    response = _original_template_response(request, name, context, *args, **kwargs)
    
    # 如果读取了闪存消息，则在返回 response 时将其立即销毁
    if flash_error:
        response.delete_cookie("flash_error")
    if flash_success:
        response.delete_cookie("flash_success")
        
    return response

templates.TemplateResponse = custom_template_response


def register_web_routes(app):
    from app.web.routes.auth import router as auth_router
    from app.web.routes.dashboard import router as dashboard_router
    from app.web.routes.accounts import router as accounts_router
    from app.web.routes.auto_reply import router as auto_reply_router
    from app.web.routes.scheduled import router as scheduled_router
    from app.web.routes.messages import router as messages_router
    from app.web.routes.files import router as files_router
    from app.web.routes.profile import router as profile_router
    from app.web.routes.repository import router as repository_router

    @app.get("/")
    async def root(request: Request):
        from app.web.routes.auth import _is_logged_in
        if _is_logged_in(request):
            return RedirectResponse(url="/web/dashboard", status_code=303)
        return templates.TemplateResponse(request, "index.html")


    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(accounts_router)
    app.include_router(auto_reply_router)
    app.include_router(scheduled_router)
    app.include_router(messages_router)
    app.include_router(files_router)
    app.include_router(profile_router)
    app.include_router(repository_router)
