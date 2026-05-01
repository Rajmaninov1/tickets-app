from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class RealtimeEvent(BaseModel):
    type: Literal["broadcast", "notification"] = "broadcast"
    channel: str = "global"
    message: str = ""
    from_user: str | None = None
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
