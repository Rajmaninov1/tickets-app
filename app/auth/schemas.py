from pydantic import BaseModel, EmailStr


class SessionUser(BaseModel):
    """Represents the authenticated user stored in the session cookie."""

    id: int
    email: EmailStr
    name: str | None = None
    avatar_url: str | None = None
