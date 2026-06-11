import os

from fastapi import APIRouter
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


def register_web_routes(app):
    from app.web.routes.auth import router as auth_router
    from app.web.routes.dashboard import router as dashboard_router
    from app.web.routes.accounts import router as accounts_router
    from app.web.routes.auto_reply import router as auto_reply_router
    from app.web.routes.scheduled import router as scheduled_router
    from app.web.routes.messages import router as messages_router
    from app.web.routes.files import router as files_router

    @app.get("/")
    async def root():
        return RedirectResponse(url="/web/dashboard", status_code=303)

    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(accounts_router)
    app.include_router(auto_reply_router)
    app.include_router(scheduled_router)
    app.include_router(messages_router)
    app.include_router(files_router)
