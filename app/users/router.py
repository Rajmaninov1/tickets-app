import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_session_user
from app.auth.schemas import SessionUser
from app.db.session import get_db
from app.users.repository import get_user_by_email, search_users
from app.users.schemas import UserRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserRead])
async def users_search(
    q: str = "",
    db: AsyncSession = Depends(get_db),
    _user: SessionUser = Depends(require_session_user),
) -> list[UserRead]:
    """Search for users by name or email."""
    if not q:
        logger.debug("users.search: empty query, returning none")
        return []
    trimmed = q.strip()
    rows = list(await search_users(db, query=q))
    logger.debug(
        "users.search: query_len=%s trimmed_len=%s results=%s", len(q), len(trimmed), len(rows)
    )
    return rows


@router.get("/me", response_model=UserRead)
async def get_current_user(
    db: AsyncSession = Depends(get_db),
    user: SessionUser = Depends(require_session_user),
):
    logger.debug("users.me: session user_id=%s", user.id)
    db_user = await get_user_by_email(db, email=user.email)
    if not db_user:
        logger.debug("users.me: no DB row for session user_id=%s", user.id)
        raise HTTPException(status_code=404, detail="User not found")
    logger.debug("users.me: resolved db_user_id=%s", db_user.id)
    return db_user
