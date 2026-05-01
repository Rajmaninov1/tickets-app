import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/")
async def root() -> dict[str, str]:
    """Root endpoint – welcome message."""
    return {"message": "Welcome to the Tickets API. Visit /docs for API documentation."}


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe – confirms the process is running."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Readiness probe – confirms the database connection is alive."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        logger.exception("Database readiness check failed.")
        return {"status": "unavailable"}
