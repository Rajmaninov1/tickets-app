from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi_sso.sso.google import GoogleSSO
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import clear_session, set_session_user
from app.core.config import get_settings
from app.db.session import get_db
from app.users.repository import upsert_user

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


def get_google_sso() -> GoogleSSO | None:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        return None
    return GoogleSSO(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=str(settings.google_redirect_uri),
        allow_insecure_http=settings.environment != "prod",
    )


@router.get("/login")
@limiter.limit("10/minute")
async def login(request: Request) -> RedirectResponse:
    sso = get_google_sso()
    if not sso:
        settings = get_settings()
        if settings.environment == "dev":
            return RedirectResponse(url="/auth/dev-login")
        raise HTTPException(
            status_code=501,
            detail="Google SSO not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )
    async with sso:
        return await sso.get_login_redirect()


@router.get("/dev-login")
async def dev_login(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    settings = get_settings()
    if settings.environment != "dev":
        raise HTTPException(status_code=403, detail="Dev login only available in dev environment")

    # Create/get a mock user
    user = await upsert_user(
        db,
        email="dev@example.com",
        name="Developer User",
        avatar_url="https://api.dicebear.com/7.x/avataaars/svg?seed=dev",
    )

    set_session_user(
        request,
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
        },
    )
    return RedirectResponse(url="/", status_code=302)


@router.get("/callback")
@limiter.limit("10/minute")
async def callback(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    sso = get_google_sso()
    if not sso:
        raise HTTPException(status_code=501, detail="Google SSO not configured")
    try:
        async with sso:
            user = await sso.verify_and_process(request)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="SSO verification failed") from exc

    email = getattr(user, "email", None)
    name = getattr(user, "display_name", None) or getattr(user, "first_name", None)
    avatar_url = getattr(user, "picture", None)
    if not email:
        raise HTTPException(status_code=400, detail="Google profile missing email")

    db_user = await upsert_user(db, email=email, name=name, avatar_url=avatar_url)

    set_session_user(
        request,
        {
            "id": db_user.id,
            "email": db_user.email,
            "name": db_user.name,
            "avatar_url": db_user.avatar_url,
        },
    )
    return RedirectResponse(url="/", status_code=302)


@router.post("/logout")
async def logout(request: Request) -> dict[str, Any]:
    clear_session(request)
    return {"ok": True}
