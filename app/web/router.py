from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["web"])

@router.get("/")
async def serve_index() -> FileResponse:
    """Serve the main frontend application."""
    return FileResponse("static/index.html")
