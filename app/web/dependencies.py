from fastapi import Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
import jwt
from app.config import get_settings

async def get_current_user_from_cookie(request: Request) -> int:
    token = request.cookies.get("web_token")
    if not token:
        raise HTTPException(status_code=303, headers={"Location": "/web/login"})
    try:
        settings = get_settings()
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        return int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=303, headers={"Location": "/web/login"})
