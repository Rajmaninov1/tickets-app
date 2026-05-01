from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.tickets.models import Comment, Ticket, TicketAttachment, TicketPriority, TicketStatus


# --- TICKETS ---


async def create_ticket(
    db: AsyncSession,
    *,
    title: str,
    description: str,
    author_id: int,
    priority: TicketPriority = TicketPriority.MEDIUM,
    status: TicketStatus = TicketStatus.OPEN,
    is_read: bool = False,
    assigned_to_id: int | None = None,
) -> Ticket:
    ticket = Ticket(
        title=title,
        description=description,
        author_id=author_id,
        priority=priority,
        status=status,
        is_read=is_read,
        assigned_to_id=assigned_to_id,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ticket


async def get_ticket_by_id(db: AsyncSession, ticket_id: int) -> Ticket | None:
    res = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id).options(selectinload(Ticket.attachments))
    )
    return res.scalar_one_or_none()


async def get_ticket_related_user_ids(
    db: AsyncSession, ticket_id: int, exclude_user_id: int | None = None
) -> list[int]:
    ticket = await get_ticket_by_id(db, ticket_id)
    if not ticket:
        return []

    user_ids = {ticket.author_id}
    if ticket.assigned_to_id:
        user_ids.add(ticket.assigned_to_id)

    res = await db.execute(select(Comment.author_id).where(Comment.ticket_id == ticket_id))
    comment_authors = res.scalars().all()
    user_ids.update(comment_authors)

    if exclude_user_id is not None and exclude_user_id in user_ids:
        user_ids.remove(exclude_user_id)

    return list(user_ids)


async def get_tickets(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    author_id: int | None = None,
    assigned_to_id: int | None = None,
    status: TicketStatus | None = None,
) -> Sequence[Ticket]:
    query = select(Ticket)

    if author_id is not None:
        query = query.where(Ticket.author_id == author_id)

    if assigned_to_id is not None:
        query = query.where(Ticket.assigned_to_id == assigned_to_id)

    if status is not None:
        query = query.where(Ticket.status == status)

    query = query.offset(skip).limit(limit).options(selectinload(Ticket.attachments))
    res = await db.execute(query)
    return res.scalars().all()


async def update_ticket(db: AsyncSession, ticket: Ticket, **kwargs) -> Ticket:
    for key, value in kwargs.items():
        if hasattr(ticket, key):
            setattr(ticket, key, value)
    await db.commit()
    await db.refresh(ticket)
    return ticket


async def delete_ticket(db: AsyncSession, ticket: Ticket) -> None:
    await db.delete(ticket)
    await db.commit()


async def mark_ticket_as_read(db: AsyncSession, ticket: Ticket) -> Ticket:
    ticket.is_read = True
    await db.commit()
    await db.refresh(ticket)
    return ticket


# --- COMMENTS ---


async def create_comment(
    db: AsyncSession, *, ticket_id: int, author_id: int, body: str, is_read: bool = False
) -> Comment:
    comment = Comment(ticket_id=ticket_id, author_id=author_id, body=body, is_read=is_read)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


async def get_comments_by_ticket_id(db: AsyncSession, ticket_id: int) -> Sequence[Comment]:
    res = await db.execute(
        select(Comment).where(Comment.ticket_id == ticket_id).order_by(Comment.created_at)
    )
    return res.scalars().all()


async def get_comment_by_id(db: AsyncSession, comment_id: int) -> Comment | None:
    res = await db.execute(select(Comment).where(Comment.id == comment_id))
    return res.scalar_one_or_none()


async def update_comment(db: AsyncSession, comment: Comment, body: str) -> Comment:
    comment.body = body
    await db.commit()
    await db.refresh(comment)
    return comment


async def delete_comment(db: AsyncSession, comment: Comment) -> None:
    await db.delete(comment)
    await db.commit()


async def mark_comment_as_read(db: AsyncSession, comment: Comment) -> Comment:
    comment.is_read = True
    await db.commit()
    await db.refresh(comment)
    return comment


# --- ATTACHMENTS ---


async def create_attachment(
    db: AsyncSession,
    *,
    ticket_id: int,
    filename: str,
    content_type: str | None,
    size_bytes: int,
    storage_path: str,
) -> TicketAttachment:
    attachment = TicketAttachment(
        ticket_id=ticket_id,
        filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
        storage_path=storage_path,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


async def get_attachments_by_ticket_id(
    db: AsyncSession, ticket_id: int
) -> Sequence[TicketAttachment]:
    res = await db.execute(
        select(TicketAttachment)
        .where(TicketAttachment.ticket_id == ticket_id)
        .order_by(TicketAttachment.created_at)
    )
    return res.scalars().all()


async def get_attachment_by_id(db: AsyncSession, attachment_id: int) -> TicketAttachment | None:
    res = await db.execute(select(TicketAttachment).where(TicketAttachment.id == attachment_id))
    return res.scalar_one_or_none()


async def delete_attachment(db: AsyncSession, attachment: TicketAttachment) -> None:
    await db.delete(attachment)
    await db.commit()
