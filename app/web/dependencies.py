from fastapi import Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db_session
from app.models.user import User
from app.config import get_settings
from app.common.exceptions import DemoRestrictionError

async def get_current_user_from_cookie(request: Request) -> int:
    token = request.cookies.get("web_token")
    if not token:
        raise HTTPException(status_code=303, headers={"Location": "/web/login"})
    try:
        settings = get_settings()
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        email = payload.get("email")
        if email and email.endswith("@test.com"):
            if request.method in ("POST", "PUT", "DELETE", "PATCH"):
                path = request.url.path
                if not (
                    path.startswith("/web/profile/email") or
                    path.startswith("/web/profile/password") or
                    "try-now" in path or
                    "logout" in path
                ):
                    raise DemoRestrictionError()
        return int(payload["sub"])
    except DemoRestrictionError:
        raise
    except Exception:
        raise HTTPException(status_code=303, headers={"Location": "/web/login"})


async def get_current_admin_from_cookie(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session)
) -> User:
    token = request.cookies.get("web_token")
    if not token:
        raise HTTPException(status_code=303, headers={"Location": "/web/login"})
    try:
        settings = get_settings()
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        user_id = int(payload["sub"])
        user = await db_session.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=303, headers={"Location": "/web/login"})
        if not user.is_admin:
            raise HTTPException(status_code=303, headers={"Location": "/web/dashboard"})
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=303, headers={"Location": "/web/login"})

