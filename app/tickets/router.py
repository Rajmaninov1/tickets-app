from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_session_user
from app.auth.schemas import SessionUser
from app.db.session import get_db
from app.tickets.models import Comment, Ticket, TicketAttachment, TicketStatus
from app.tickets.repository import (
    create_attachment,
    create_comment,
    create_ticket,
    delete_attachment,
    delete_comment,
    delete_ticket,
    get_attachment_by_id,
    get_attachments_by_ticket_id,
    get_comment_by_id,
    get_comments_by_ticket_id,
    get_ticket_by_id,
    get_ticket_related_user_ids,
    get_tickets,
    update_ticket,
)
from app.tickets.schemas import (
    AttachmentRead,
    CommentCreate,
    CommentRead,
    TicketCreate,
    TicketRead,
    TicketUpdate,
)
from app.tickets.storage import save_ticket_attachment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketRead])
async def tickets_list(
    db: AsyncSession = Depends(get_db),
    author_id: int | None = None,
    assigned_to_id: int | None = None,
    status: TicketStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Ticket]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    return list(
        await get_tickets(
            db,
            author_id=author_id,
            assigned_to_id=assigned_to_id,
            status=status if status else None,
            limit=limit,
            skip=offset,
        )
    )


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
async def tickets_create(
    request: Request,
    payload: TicketCreate,
    db: AsyncSession = Depends(get_db),
    user: SessionUser = Depends(require_session_user),
) -> Ticket:
    try:
        ticket = await create_ticket(
            db,
            title=payload.title,
            description=payload.description,
            author_id=user.id,
            assigned_to_id=payload.assigned_to_id,
            status=payload.status,
            priority=payload.priority,
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid assigned_to_id: user does not exist",
        ) from None
    related_users = await get_ticket_related_user_ids(db, ticket.id, exclude_user_id=user.id)
    if related_users:
        pass  # for future notifications
    return ticket


@router.get("/{ticket_id}", response_model=TicketRead)
async def tickets_get(ticket_id: int, db: AsyncSession = Depends(get_db)) -> Ticket:
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.patch("/{ticket_id}", response_model=TicketRead)
async def tickets_update(
    request: Request,
    ticket_id: int,
    payload: TicketUpdate,
    db: AsyncSession = Depends(get_db),
    user: SessionUser = Depends(require_session_user),
) -> Ticket:
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    data = payload.model_dump(exclude_unset=True)
    try:
        updated_ticket = await update_ticket(db, ticket, **data)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid assigned_to_id: user does not exist",
        ) from None

    related_users = await get_ticket_related_user_ids(
        db, updated_ticket.id, exclude_user_id=user.id
    )
    if related_users:
        pass  # for future notifications
    return updated_ticket


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def tickets_delete(ticket_id: int, db: AsyncSession = Depends(get_db)) -> None:
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    await delete_ticket(db, ticket)


@router.get("/{ticket_id}/comments", response_model=list[CommentRead])
async def comments_list(ticket_id: int, db: AsyncSession = Depends(get_db)) -> list[Comment]:
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return list(await get_comments_by_ticket_id(db, ticket_id))


@router.post(
    "/{ticket_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED
)
async def comments_create(
    request: Request,
    ticket_id: int,
    payload: CommentCreate,
    db: AsyncSession = Depends(get_db),
    user: SessionUser = Depends(require_session_user),
) -> Comment:
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    comment = await create_comment(db, ticket_id=ticket_id, author_id=user.id, body=payload.body)

    related_users = await get_ticket_related_user_ids(db, ticket_id, exclude_user_id=user.id)
    if related_users:
        pass  # for future notifications

    return comment


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def comments_delete(comment_id: int, db: AsyncSession = Depends(get_db)) -> None:
    comment = await get_comment_by_id(db, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    await delete_comment(db, comment)


@router.get("/{ticket_id}/attachments", response_model=list[AttachmentRead])
async def attachments_list(
    ticket_id: int, db: AsyncSession = Depends(get_db)
) -> list[TicketAttachment]:
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return list(await get_attachments_by_ticket_id(db, ticket_id))


@router.post(
    "/{ticket_id}/attachments",
    response_model=list[AttachmentRead],
    status_code=status.HTTP_201_CREATED,
)
async def attachments_upload(
    ticket_id: int,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    _user: SessionUser = Depends(require_session_user),
) -> list[TicketAttachment]:
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    attachments = []
    for file in files:
        filename, content_type, size_bytes, storage_path = await save_ticket_attachment(
            ticket_id=ticket_id, file=file
        )

        att = await create_attachment(
            db,
            ticket_id=ticket_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
        )
        attachments.append(att)
    return attachments


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def attachments_delete(attachment_id: int, db: AsyncSession = Depends(get_db)) -> None:
    att = await get_attachment_by_id(db, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    path = Path(att.storage_path)
    try:
        path.unlink(missing_ok=True)
    except Exception:
        logger.warning("Failed to delete attachment file at %s", att.storage_path, exc_info=True)

    await delete_attachment(db, att)
