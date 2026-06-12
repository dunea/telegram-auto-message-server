from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_auth_service
from app.config import get_settings
from app.service.auth_service import AuthService
from app.web import templates
from app.web.dependencies import get_current_user_from_cookie
from app.repository.user_repository import SqlAlchemyUserRepository

router = APIRouter(prefix="/web", tags=["web-profile"])


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    user_id: int = Depends(get_current_user_from_cookie),
    db_session: AsyncSession = Depends(get_db_session),
    email_success: bool = False,
    password_success: bool = False,
    error: str = None,
):
    user_repo = SqlAlchemyUserRepository(db_session)
    user = await user_repo.FindById(user_id)
    if not user:
        response = RedirectResponse(url="/web/login", status_code=303)
        response.delete_cookie("web_token")
        return response

    return templates.TemplateResponse(
        request,
        "profile/index.html",
        {
            "user": user,
            "email_success": email_success,
            "password_success": password_success,
            "error": error,
        }
    )


@router.post("/profile/email")
async def update_email(
    request: Request,
    new_email: str = Form(...),
    user_id: int = Depends(get_current_user_from_cookie),
    auth_service: AuthService = Depends(get_auth_service),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        result = await auth_service.UpdateUserEmail(user_id=user_id, new_email=new_email)
        response = RedirectResponse(url="/web/profile?email_success=true", status_code=303)
        response.set_cookie(
            "web_token",
            result["access_token"],
            httponly=True,
            max_age=int(result["expires_in_seconds"]),
        )
        return response
    except Exception as e:
        user_repo = SqlAlchemyUserRepository(db_session)
        user = await user_repo.FindById(user_id)
        return templates.TemplateResponse(
            request,
            "profile/index.html",
            {
                "user": user,
                "error": str(e),
            }
        )


@router.post("/profile/password")
async def update_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    user_id: int = Depends(get_current_user_from_cookie),
    auth_service: AuthService = Depends(get_auth_service),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        result = await auth_service.UpdateUserPassword(
            user_id=user_id, old_password=old_password, new_password=new_password
        )
        response = RedirectResponse(url="/web/profile?password_success=true", status_code=303)
        response.set_cookie(
            "web_token",
            result["access_token"],
            httponly=True,
            max_age=int(result["expires_in_seconds"]),
        )
        return response
    except Exception as e:
        user_repo = SqlAlchemyUserRepository(db_session)
        user = await user_repo.FindById(user_id)
        return templates.TemplateResponse(
            request,
            "profile/index.html",
            {
                "user": user,
                "error": str(e),
            }
        )
