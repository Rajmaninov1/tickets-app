import asyncio
import json
import logging

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from app.realtime.events import RealtimeEvent
from app.realtime.hub import RealtimeHub

logger = logging.getLogger(__name__)


class RabbitBroker:
    def __init__(self, url: str, *, hub: RealtimeHub) -> None:
        self._url = url
        self._hub = hub
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._queue: aio_pika.abc.AbstractQueue | None = None
        self._consumer_tag: str | None = None
        self._ready = asyncio.Event()

        self.exchange_name = "realtime.events"
        self.queue_name = "realtime.events.queue"
        self.routing_key = "realtime"

    async def start(self) -> None:
        logger.debug(
            "RabbitBroker.start: connecting (exchange=%s queue=%s)",
            self.exchange_name,
            self.queue_name,
        )
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()

        exchange = await self._channel.declare_exchange(
            self.exchange_name,
            aio_pika.ExchangeType.FANOUT,
            durable=True,
        )
        self._queue = await self._channel.declare_queue(self.queue_name, durable=True)
        await self._queue.bind(exchange, routing_key=self.routing_key)
        self._consumer_tag = await self._queue.consume(self._on_message, no_ack=False)
        self._ready.set()
        logger.debug("RabbitBroker.start: consumer ready (routing_key=%s)", self.routing_key)

    async def stop(self) -> None:
        logger.debug("RabbitBroker.stop")
        if self._queue and self._consumer_tag:
            await self._queue.cancel(self._consumer_tag)
        if self._channel:
            await self._channel.close()
        if self._connection:
            await self._connection.close()

    async def publish(self, event: RealtimeEvent) -> None:
        await self._ready.wait()
        if not self._channel:
            raise RuntimeError("RabbitBroker not started")

        logger.debug(
            "RabbitBroker.publish type=%s channel=%s",
            event.type,
            event.channel,
        )
        exchange = await self._channel.get_exchange(self.exchange_name)
        body = event.model_dump_json().encode("utf-8")
        await exchange.publish(
            aio_pika.Message(body=body, content_type="application/json"),
            routing_key=self.routing_key,
        )

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        async with message.process(requeue=False):
            try:
                payload = json.loads(message.body.decode("utf-8"))
                event = RealtimeEvent.model_validate(payload)
            except Exception:  # noqa: BLE001
                logger.debug(
                    "RabbitBroker: dropped invalid realtime message payload", exc_info=True
                )
                return

            logger.debug(
                "RabbitBroker.consume type=%s channel=%s ws_targets_next=hub.broadcast",
                event.type,
                event.channel,
            )
            await self._hub.broadcast(event.channel, event.model_dump_json())
