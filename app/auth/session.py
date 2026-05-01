import logging
from typing import Any

from fastapi import Request

from app.auth.schemas import SessionUser

logger = logging.getLogger(__name__)


def set_session_user(request: Request, user: dict[str, Any]) -> None:
    request.session["user"] = user


def clear_session(request: Request) -> None:
    request.session.clear()


def get_current_user_from_session(request: Request) -> SessionUser | None:
    raw = request.session.get("user")
    if not raw or not isinstance(raw, dict):
        return None
    try:
        return SessionUser.model_validate(raw)
    except Exception:  # noqa: BLE001
        logger.debug(
            "get_current_user_from_session: invalid user payload for SessionUser", exc_info=True
        )
        return None
