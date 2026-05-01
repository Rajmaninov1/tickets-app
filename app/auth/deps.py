from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status

from app.auth.schemas import SessionUser
from app.auth.session import get_current_user_from_session

logger = logging.getLogger(__name__)


def require_session_user(request: Request) -> SessionUser:
    """FastAPI dependency that enforces authentication via session cookie.

    Returns the validated `SessionUser` or raises HTTP 401.
    """
    user = get_current_user_from_session(request)
    if not user:
        logger.debug(
            "require_session_user: no valid session path=%s",
            request.url.path,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
