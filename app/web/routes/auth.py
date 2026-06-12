import jwt
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api.deps import get_auth_service
from app.config import get_settings
from app.service.auth_service import AuthService
from app.web import templates

router = APIRouter(prefix="/web", tags=["web-auth"])


def _is_logged_in(request: Request) -> bool:
    """检查用户是否已经通过 cookie 登录。"""
    token = request.cookies.get("web_token")
    if not token:
        return False
    try:
        settings = get_settings()
        jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return True
    except Exception:
        return False


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, registered: bool = False):
    if _is_logged_in(request):
        return RedirectResponse(url="/web/dashboard", status_code=303)
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {"registered": registered}
    )


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        result = await auth_service.LoginUser(email=email, password=password)
        token = result["access_token"]
        response = RedirectResponse(url="/web/dashboard", status_code=303)
        response.set_cookie("web_token", token, httponly=True)
        return response
    except Exception as e:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"error": str(e)}
        )


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if _is_logged_in(request):
        return RedirectResponse(url="/web/dashboard", status_code=303)
    return templates.TemplateResponse(request, "auth/register.html")


@router.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        await auth_service.RegisterUser(email=email, password=password)
        return RedirectResponse(url="/web/login?registered=true", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"error": str(e)}
        )


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/web/login", status_code=303)
    response.delete_cookie("web_token")
    return response
