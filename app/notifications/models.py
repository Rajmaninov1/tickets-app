from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    # This many-to-many architecture is used so a single notification (like a massive system alert)
    # can be linked to hundreds of users efficiently without duplicating the payload.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text())
    action_url: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list["NotificationUser"]] = relationship(
        "NotificationUser",
        back_populates="notification",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class NotificationUser(Base):
    __tablename__ = "notification_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    is_read: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")

    notification: Mapped["Notification"] = relationship("Notification", back_populates="users")
    user = relationship("User")
