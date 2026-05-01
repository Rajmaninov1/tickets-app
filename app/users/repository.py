from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    res = await db.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()


async def search_users(db: AsyncSession, query: str, limit: int = 20) -> Sequence[User]:
    """Search users by name or email using case-insensitive partial match."""
    stmt = (
        select(User)
        .where(or_(User.name.ilike(f"%{query}%"), User.email.ilike(f"%{query}%")))
        .limit(limit)
    )
    res = await db.execute(stmt)
    return res.scalars().all()


async def upsert_user(
    db: AsyncSession, *, email: str, name: str | None, avatar_url: str | None = None
) -> User:
    """Atomically insert or update a user by email.

    Uses PostgreSQL ON CONFLICT DO UPDATE to avoid race conditions when two
    concurrent Google SSO callbacks arrive for the same email address.
    """
    stmt = (
        insert(User)
        .values(email=email, name=name, avatar_url=avatar_url)
        .on_conflict_do_update(
            index_elements=["email"],
            set_={"name": name, "avatar_url": avatar_url},
        )
        .returning(User)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one()
