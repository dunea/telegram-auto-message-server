"""产品核心功能落地页 Web 路由模块。

为未登录用户和搜索引擎提供丰富的功能详情展示页，利于 SEO 优化。
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web import templates

router = APIRouter(prefix="/web/features", tags=["web-features"])


@router.get("/hosting", response_class=HTMLResponse)
async def hosting_feature_page(request: Request):
    """渲染多账号托管与独立代理详情页。"""
    return templates.TemplateResponse(request, "features/hosting.html")


@router.get("/auto-reply", response_class=HTMLResponse)
async def auto_reply_feature_page(request: Request):
    """渲染关键词智能自动回复详情页。"""
    return templates.TemplateResponse(request, "features/auto_reply.html")


@router.get("/scheduled", response_class=HTMLResponse)
async def scheduled_feature_page(request: Request):
    """渲染 Cron 定时群发与媒体管理详情页。"""
    return templates.TemplateResponse(request, "features/scheduled.html")
