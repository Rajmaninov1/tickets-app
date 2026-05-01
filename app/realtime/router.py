import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth.session import get_current_user_from_session
from app.realtime.events import RealtimeEvent

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logger.debug("WebSocket accepted path=%s", ws.url.path)

    user = get_current_user_from_session(ws)
    if user:
        await ws.send_text(json.dumps({"type": "info", "message": f"connected as {user.name}"}))
    else:
        await ws.send_text(json.dumps({"type": "info", "message": "connected as guest"}))

    from_user = user.name if user else None

    hub = ws.app.state.hub
    broker = ws.app.state.broker

    await hub.join("global", ws)
    channels = ["global"]
    if user:
        uch = f"user_{user.id}"
        await hub.join(uch, ws)
        channels.append(uch)
    logger.debug("WebSocket subscribed channels=%s has_broker=%s", channels, broker is not None)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except Exception:  # noqa: BLE001
                payload = {"type": "broadcast", "channel": "global", "message": raw}

            if payload.get("type") != "broadcast":
                logger.debug(
                    "WebSocket ignoring non-broadcast payload keys=%s", list(payload.keys())
                )
                continue

            event = RealtimeEvent(
                type="broadcast",
                channel=str(payload.get("channel") or "global"),
                message=str(payload.get("message") or ""),
                from_user=from_user,
            )
            if broker:
                logger.debug(
                    "WebSocket client broadcast -> broker channel=%s len(message)=%s",
                    event.channel,
                    len(event.message),
                )
                await broker.publish(event)
            else:
                logger.warning("Realtime broker not available, skipping broadcast")
    except WebSocketDisconnect:
        logger.debug("WebSocketDisconnect, leaving hub")
        await hub.leave_all(ws)
