from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_session_user
from app.auth.schemas import SessionUser
from app.db.session import get_db
from app.users.repository import get_user_by_email, search_users
from app.users.schemas import UserRead

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserRead])
async def users_search(
    q: str = "",
    db: AsyncSession = Depends(get_db),
    _user: SessionUser = Depends(require_session_user),
) -> list[UserRead]:
    """Search for users by name or email."""
    if not q:
        return []
    return list(await search_users(db, query=q))


@router.get("/me", response_model=UserRead)
async def get_current_user(
    db: AsyncSession = Depends(get_db),
    user: SessionUser = Depends(require_session_user),
):
    db_user = await get_user_by_email(db, email=user.email)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user
