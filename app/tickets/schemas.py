from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.tickets.models import TicketPriority, TicketStatus


class UserRef(BaseModel):
    id: int
    email: str
    name: str | None = None


class TicketCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    assigned_to_id: int = Field(gt=0)
    status: TicketStatus
    priority: TicketPriority


class TicketUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    assigned_to_id: int | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None

    @field_validator("assigned_to_id", mode="before")
    @classmethod
    def validate_assigned_to_id(cls, v: int | None) -> int | None:
        if v == 0:
            return None
        return v


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    author_id: int
    assigned_to_id: int
    status: TicketStatus
    priority: TicketPriority
    is_read: bool
    created_at: datetime
    updated_at: datetime
    attachments: list[AttachmentRead] = []


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    author_id: int
    body: str
    is_read: bool
    created_at: datetime


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    filename: str
    content_type: str | None
    size_bytes: int
    storage_path: str
    created_at: datetime
