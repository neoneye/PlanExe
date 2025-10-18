"""Utility for relaying conversation streaming events over SSE."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator, Dict, Iterable, Optional


class ConversationSSEManager:
    """Bridge conversation harness events to Server-Sent Events."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[Optional[Dict[str, str]]] = asyncio.Queue()
        self._loop = asyncio.get_event_loop()
        self._closed = False

    def push(self, events: Iterable[Dict[str, object]]) -> None:
        """Schedule events to be emitted over SSE."""

        for event in events:
            if not event:
                continue
            payload = {
                "event": event.get("event", "message"),
                "data": json.dumps(event.get("data", {})),
            }
            asyncio.run_coroutine_threadsafe(self._queue.put(payload), self._loop)

    async def stream(self) -> AsyncGenerator[Dict[str, str], None]:
        """Yield events suitable for EventSourceResponse."""

        while True:
            item = await self._queue.get()
            if item is None:
                break
            yield item

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self._queue.put(None)
