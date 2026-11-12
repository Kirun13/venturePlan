"""Task-local event reporting shared by graph nodes and provider calls."""
from contextvars import ContextVar
from typing import Awaitable, Callable

EventSink = Callable[[str, str | None, dict, str], Awaitable[None]]
event_sink: ContextVar[EventSink | None] = ContextVar("event_sink", default=None)

async def report(kind: str, node: str | None = None, details: dict | None = None, message: str = ""):
    sink = event_sink.get()
    if sink is not None:
        await sink(kind, node, details or {}, message)
