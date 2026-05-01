from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_session_user
from app.auth.schemas import SessionUser
from app.db.session import get_db
from app.notifications.repository import create_massive_notification
from app.realtime.events import RealtimeEvent
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


async def _notify_users(
    db: AsyncSession,
    request: Request,
    user_ids: list[int],
    message: str,
    action_url: str,
    n_type: str,
) -> None:
    if not user_ids:
        return

    broker = request.app.state.broker
    logger.debug(
        "tickets.notify: type=%s recipients=%s realtime_broker=%s",
        n_type,
        len(user_ids),
        broker is not None,
    )

    # 1. Save notification to database
    await create_massive_notification(
        db, user_ids=user_ids, message=message, action_url=action_url, type=n_type
    )
    # 2. Publish realtime event to the specific channels
    if broker:
        for uid in user_ids:
            event = RealtimeEvent(
                type="notification",
                channel=f"user_{uid}",
                message=message,
            )
            try:
                await broker.publish(event)
            except Exception:
                logger.warning("Failed to publish realtime notification to RabbitMQ", exc_info=True)


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
    logger.debug(
        "tickets.list: author_id=%s assigned_to_id=%s status=%s limit=%s offset=%s",
        author_id,
        assigned_to_id,
        getattr(status, "value", status),
        limit,
        offset,
    )
    rows = list(
        await get_tickets(
            db,
            author_id=author_id,
            assigned_to_id=assigned_to_id,
            status=status if status else None,
            limit=limit,
            skip=offset,
        )
    )
    logger.debug("tickets.list: returned %s row(s)", len(rows))
    return rows


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
    logger.debug(
        "tickets.create: ticket_id=%s author_id=%s assigned_to_id=%s status=%s priority=%s",
        ticket.id,
        ticket.author_id,
        ticket.assigned_to_id,
        ticket.status.value,
        ticket.priority.value,
    )
    related_users = await get_ticket_related_user_ids(db, ticket.id, exclude_user_id=user.id)
    if related_users:
        await _notify_users(
            db,
            request,
            user_ids=related_users,
            message=f"You are involved in a new ticket: {ticket.title}",
            action_url=f"/tickets/{ticket.id}",
            n_type="ticket_created",
        )
    return ticket


@router.get("/{ticket_id}", response_model=TicketRead)
async def tickets_get(ticket_id: int, db: AsyncSession = Depends(get_db)) -> Ticket:
    logger.debug("tickets.get: ticket_id=%s", ticket_id)
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        logger.debug("tickets.get: not_found ticket_id=%s", ticket_id)
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
        logger.debug("tickets.patch: not_found ticket_id=%s actor_id=%s", ticket_id, user.id)
        raise HTTPException(status_code=404, detail="Ticket not found")

    old_status = ticket.status

    data = payload.model_dump(exclude_unset=True)
    logger.debug(
        "tickets.patch: ticket_id=%s actor_id=%s fields=%s old_status=%s",
        ticket_id,
        user.id,
        sorted(data.keys()),
        old_status.value,
    )
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
        if old_status != updated_ticket.status:
            await _notify_users(
                db,
                request,
                user_ids=related_users,
                message="Ticket status changed to "
                f"{updated_ticket.status.value}: {updated_ticket.title}",
                action_url=f"/tickets/{updated_ticket.id}",
                n_type="ticket_status_changed",
            )
        else:
            await _notify_users(
                db,
                request,
                user_ids=related_users,
                message=f"Ticket updated: {updated_ticket.title}",
                action_url=f"/tickets/{updated_ticket.id}",
                n_type="ticket_updated",
            )
    logger.debug(
        "tickets.patch: done ticket_id=%s new_status=%s",
        updated_ticket.id,
        updated_ticket.status.value,
    )
    return updated_ticket


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def tickets_delete(ticket_id: int, db: AsyncSession = Depends(get_db)) -> None:
    logger.debug("tickets.delete: ticket_id=%s", ticket_id)
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        logger.debug("tickets.delete: not_found ticket_id=%s", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")
    await delete_ticket(db, ticket)
    logger.debug("tickets.delete: done ticket_id=%s", ticket_id)


@router.get("/{ticket_id}/comments", response_model=list[CommentRead])
async def comments_list(ticket_id: int, db: AsyncSession = Depends(get_db)) -> list[Comment]:
    logger.debug("tickets.comments.list: ticket_id=%s", ticket_id)
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    rows = list(await get_comments_by_ticket_id(db, ticket_id))
    logger.debug("tickets.comments.list: ticket_id=%s count=%s", ticket_id, len(rows))
    return rows


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
    logger.debug(
        "tickets.comments.create: comment_id=%s ticket_id=%s author_id=%s body_len=%s",
        comment.id,
        ticket_id,
        user.id,
        len(payload.body),
    )

    related_users = await get_ticket_related_user_ids(db, ticket_id, exclude_user_id=user.id)
    if related_users:
        await _notify_users(
            db,
            request,
            user_ids=related_users,
            message=f"New comment on ticket: {ticket.title}",
            action_url=f"/tickets/{ticket.id}#comment-{comment.id}",
            n_type="comment_created",
        )

    return comment


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def comments_delete(comment_id: int, db: AsyncSession = Depends(get_db)) -> None:
    logger.debug("tickets.comments.delete: comment_id=%s", comment_id)
    comment = await get_comment_by_id(db, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    tid = comment.ticket_id
    await delete_comment(db, comment)
    logger.debug("tickets.comments.delete: done comment_id=%s ticket_id=%s", comment_id, tid)


@router.get("/{ticket_id}/attachments", response_model=list[AttachmentRead])
async def attachments_list(
    ticket_id: int, db: AsyncSession = Depends(get_db)
) -> list[TicketAttachment]:
    logger.debug("tickets.attachments.list: ticket_id=%s", ticket_id)
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    rows = list(await get_attachments_by_ticket_id(db, ticket_id))
    logger.debug("tickets.attachments.list: ticket_id=%s count=%s", ticket_id, len(rows))
    return rows


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

    logger.debug(
        "tickets.attachments.upload: ticket_id=%s files=%s actor_id=%s",
        ticket_id,
        len(files),
        _user.id,
    )
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
        logger.debug(
            "tickets.attachments.upload: saved attachment_id=%s filename=%s size_bytes=%s",
            att.id,
            att.filename,
            att.size_bytes,
        )
    return attachments


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def attachments_delete(attachment_id: int, db: AsyncSession = Depends(get_db)) -> None:
    logger.debug("tickets.attachments.delete: attachment_id=%s", attachment_id)
    att = await get_attachment_by_id(db, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    path = Path(att.storage_path)
    try:
        path.unlink(missing_ok=True)
    except Exception:
        logger.warning("Failed to delete attachment file at %s", att.storage_path, exc_info=True)

    await delete_attachment(db, att)
    logger.debug(
        "tickets.attachments.delete: done attachment_id=%s ticket_id=%s",
        attachment_id,
        att.ticket_id,
    )
