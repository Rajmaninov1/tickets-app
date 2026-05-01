from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.auth.schemas import SessionUser
from app.auth.session import get_current_user_from_session


def require_session_user(request: Request) -> SessionUser:
    """FastAPI dependency that enforces authentication via session cookie.

    Returns the validated `SessionUser` or raises HTTP 401.
    """
    user = get_current_user_from_session(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
