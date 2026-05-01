from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NotificationCreate(BaseModel):
    message: str = Field(min_length=1)
    action_url: str = ""
    type: str = "info"

    # Optional fields to target specific users
    user_id: int | None = None
    user_ids: list[int] | None = None


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notification_id: int
    is_read: bool
    message: str
    action_url: str | None
    type: str
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def flatten_notification(cls, data: Any) -> Any:
        if hasattr(data, "notification") and data.notification:
            return {
                "notification_id": data.notification_id,
                "is_read": data.is_read,
                "message": data.notification.message,
                "action_url": data.notification.action_url,
                "type": data.notification.type,
                "created_at": data.notification.created_at,
            }
        return data
