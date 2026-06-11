from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

web_router = APIRouter(prefix="/web")
templates = Jinja2Templates(directory="templates")

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
