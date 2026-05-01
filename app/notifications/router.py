from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_session_user
from app.auth.schemas import SessionUser
from app.db.session import get_db
from app.notifications.repository import (
    create_massive_notification,
    create_personal_notification,
    get_unread_notifications_count,
    get_user_notifications,
    mark_notification_as_read,
)
from app.notifications.schemas import NotificationCreate, NotificationRead

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
async def notifications_list(
    db: AsyncSession = Depends(get_db),
    user: SessionUser = Depends(require_session_user),
    skip: int = 0,
    limit: int = 50,
    unread_only: bool = False,
):
    notifications = await get_user_notifications(
        db, user_id=user.id, skip=skip, limit=limit, unread_only=unread_only
    )
    return notifications


@router.get("/unread-count")
async def unread_notifications_count(
    db: AsyncSession = Depends(get_db),
    user: SessionUser = Depends(require_session_user),
) -> dict[str, int]:
    count = await get_unread_notifications_count(db, user_id=user.id)
    return {"count": count}


@router.patch("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def notifications_mark_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    user: SessionUser = Depends(require_session_user),
):
    try:
        await mark_notification_as_read(db, notification_id=notification_id, user_id=user.id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Notification not found") from None


@router.post("", status_code=status.HTTP_201_CREATED)
async def notifications_create(
    payload: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    _user: SessionUser = Depends(require_session_user),
):
    if payload.user_ids:
        # Return the underlying Notification, but we don't have a read schema
        # for the raw notification
        # The frontend doesn't need to read the raw one usually, just the NotificationUser mappings.
        await create_massive_notification(
            db,
            user_ids=payload.user_ids,
            message=payload.message,
            action_url=payload.action_url,
            type=payload.type,
        )
        return {"detail": "Massive notification sent"}
    elif payload.user_id:
        await create_personal_notification(
            db,
            user_id=payload.user_id,
            message=payload.message,
            action_url=payload.action_url,
            type=payload.type,
        )
        return {"detail": "Personal notification sent"}
    else:
        raise HTTPException(status_code=400, detail="Must specify user_id or user_ids")
