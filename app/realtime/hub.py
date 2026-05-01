import asyncio
import logging
from collections import defaultdict

from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)


class RealtimeHub:
    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def join(self, channel: str, ws: WebSocket) -> None:
        async with self._lock:
            self._channels[channel].add(ws)
            n = len(self._channels[channel])
        logger.debug("RealtimeHub.join channel=%s subscribers=%s", channel, n)

    async def leave_all(self, ws: WebSocket) -> None:
        async with self._lock:
            for ch in list(self._channels.keys()):
                self._channels[ch].discard(ws)
                if not self._channels[ch]:
                    self._channels.pop(ch, None)
        logger.debug("RealtimeHub.leave_all")

    async def broadcast(self, channel: str, message: str) -> None:
        async with self._lock:
            targets = list(self._channels.get(channel, set()))

        logger.debug("RealtimeHub.broadcast channel=%s recipients=%s", channel, len(targets))
        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:  # noqa: BLE001
                await self.leave_all(ws)
