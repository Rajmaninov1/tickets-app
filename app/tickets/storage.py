from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10MB


async def save_ticket_attachment(
    *, ticket_id: int, file: UploadFile
) -> tuple[str, str | None, int, str]:
    settings = get_settings()

    base_dir: Path = settings.upload_dir / "tickets" / str(ticket_id)
    base_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file.filename or "attachment.bin").name
    token = secrets.token_hex(8)
    target = base_dir / f"{token}_{safe_name}"

    size = 0
    with target.open("wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_ATTACHMENT_BYTES:
                try:
                    target.unlink(missing_ok=True)
                except Exception:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Attachment too large (max 10MB)",
                )
            f.write(chunk)

    return safe_name, file.content_type, size, str(target.as_posix())
