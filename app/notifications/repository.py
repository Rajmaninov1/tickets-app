from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.notifications.models import Notification, NotificationUser


async def create_personal_notification(
    db: AsyncSession, *, user_id: int, message: str, action_url: str, type: str
) -> Notification:
    notification = Notification(message=message, action_url=action_url, type=type)
    db.add(notification)
    await db.flush()  # Flush to get the notification.id

    notification_user = NotificationUser(notification_id=notification.id, user_id=user_id)
    db.add(notification_user)
    await db.commit()
    await db.refresh(notification)
    return notification


async def create_massive_notification(
    db: AsyncSession, *, user_ids: list[int], message: str, action_url: str, type: str
) -> Notification:
    notification = Notification(message=message, action_url=action_url, type=type)
    db.add(notification)
    await db.flush()  # Flush to get the notification.id

    # Create an association for each user efficiently
    notification_users = [
        NotificationUser(notification_id=notification.id, user_id=uid) for uid in user_ids
    ]
    db.add_all(notification_users)
    await db.commit()
    await db.refresh(notification)
    return notification


async def get_user_notifications(
    db: AsyncSession,
    user_id: int,
    *,
    skip: int = 0,
    limit: int = 50,
    unread_only: bool = False,
) -> Sequence[NotificationUser]:
    # We query NotificationUser to get the is_read status,
    # and eagerly load the Notification payload so we have the message/url.
    query = select(NotificationUser).options(joinedload(NotificationUser.notification))

    query = query.where(NotificationUser.user_id == user_id)

    if unread_only:
        query = query.where(NotificationUser.is_read.is_(False))

    # Order by the related notification's creation date
    query = (
        query.join(NotificationUser.notification)
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    res = await db.execute(query)
    return res.scalars().all()


async def get_unread_notifications_count(db: AsyncSession, user_id: int) -> int:
    query = select(func.count(NotificationUser.id)).where(
        NotificationUser.user_id == user_id,
        NotificationUser.is_read.is_(False),
    )
    res = await db.execute(query)
    return res.scalar_one()


async def mark_notification_as_read(db: AsyncSession, notification_id: int, user_id: int) -> None:
    # Update only the specific user's read status for this notification
    query = (
        update(NotificationUser)
        .where(
            NotificationUser.notification_id == notification_id,
            NotificationUser.user_id == user_id,
        )
        .values(is_read=True)
    )
    result = await db.execute(query)
    await db.commit()

    if result.rowcount == 0:
        raise ValueError(f"Notification {notification_id} not found for user {user_id}")


async def delete_old_notifications(db: AsyncSession, older_than_days: int = 30) -> int:
    """
    Deletes notifications older than X days.
    Because of CASCADE ON DELETE in the DB, this automatically deletes the
    associated records in the notification_users table.
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)

    query = (
        delete(Notification).where(Notification.created_at < cutoff_date).returning(Notification.id)
    )
    res = await db.execute(query)
    await db.commit()

    # Return how many were deleted
    deleted_ids = res.scalars().all()
    return len(deleted_ids)
