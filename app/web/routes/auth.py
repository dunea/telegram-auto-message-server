import jwt
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api.deps import get_auth_service
from app.config import get_settings
from app.service.auth_service import AuthService
from app.web import templates
from app.common.rate_limiter import rate_limiter
from app.common.exceptions import RateLimitError

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
        
        settings = get_settings()
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        is_admin = payload.get("is_admin", False)
        
        redirect_url = "/web/select-role" if is_admin else "/web/dashboard"
        response = RedirectResponse(url=redirect_url, status_code=303)
        response.set_cookie(
            "web_token",
            token,
            httponly=True,
            max_age=int(result["expires_in_seconds"]),
        )
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
        from urllib.parse import quote
        response = RedirectResponse(url="/web/login", status_code=303)
        response.set_cookie("flash_success", quote("注册成功，请使用邮箱和密码登录。"), max_age=10)
        return response
    except Exception as e:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"error": str(e)}
        )


@router.post("/logout")
async def logout():
    response = RedirectResponse(url="/web/login", status_code=303)
    response.delete_cookie("web_token")
    return response


@router.post("/auth/try-now")
async def try_now(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    import string
    import random
    
    chars = string.ascii_lowercase + string.digits
    random_str = "".join(random.choices(chars, k=6))
    email = f"{random_str}@test.com"
    password = "123456"
    
    try:
        # 获取客户端 IP 并进行免注册登录限速校验
        client_ip = request.client.host if request.client else "unknown"
        is_allowed, error_msg = rate_limiter.check_and_record(client_ip)
        if not is_allowed:
            raise RateLimitError(error_msg)

        await auth_service.RegisterUser(email=email, password=password)
        result = await auth_service.LoginUser(email=email, password=password)
        token = result["access_token"]
        response = RedirectResponse(url="/web/dashboard", status_code=303)
        response.set_cookie(
            "web_token",
            token,
            httponly=True,
            max_age=int(result["expires_in_seconds"]),
        )
        return response
    except RateLimitError as e:
        import urllib.parse
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie("flash_error", urllib.parse.quote(str(e)), max_age=10)
        return response
    except Exception as e:
        from urllib.parse import quote
        response = RedirectResponse(url="/web/login", status_code=303)
        response.set_cookie("flash_error", quote(str(e)), max_age=10)
        return response

