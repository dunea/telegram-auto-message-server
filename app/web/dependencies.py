from fastapi import Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
import jwt
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

