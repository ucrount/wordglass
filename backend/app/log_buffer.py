"""Per-process in-memory ring buffers for diagnostic logs.

Two separate buffers:
  - AI_CALLS: structured records of each AI request (max 50)
  - SYSTEM_LOGS: structured events from log_event (max 200)

Single-process by design — we don't need cross-worker fanout for a single-VPS
deployment. Both are cleared on process restart (intentional: keeps the
buffers cheap, encourages diagnostic-first usage rather than archival).
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from typing import Any, AsyncIterator


_AI_LOCK = threading.Lock()
_AI_BUFFER: deque[dict[str, Any]] = deque(maxlen=50)
_AI_COUNTER = 0

_SYSLOG_LOCK = threading.Lock()
_SYSLOG_BUFFER: deque[dict[str, Any]] = deque(maxlen=200)
_SYSLOG_COUNTER = 0

# Per-process broadcast for streaming. Subscribers add an asyncio.Queue;
# push_system writes to all of them.
_SUBSCRIBERS: set["asyncio.Queue[dict[str, Any]]"] = set()


def add_ai_call(record: dict[str, Any]) -> None:
    """Add one AI call record. Assigns a monotonic id."""
    global _AI_COUNTER
    with _AI_LOCK:
        _AI_COUNTER += 1
        rec = {"id": _AI_COUNTER, "ts": time.time(), **record}
        _AI_BUFFER.append(rec)


def get_ai_calls(limit: int = 50, kind: str | None = None) -> list[dict[str, Any]]:
    """Return AI calls newest-first, optionally filtered by kind."""
    with _AI_LOCK:
        items = list(_AI_BUFFER)
    items.reverse()
    if kind:
        items = [r for r in items if r.get("kind") == kind]
    return items[:limit]


def clear_ai_calls() -> None:
    with _AI_LOCK:
        _AI_BUFFER.clear()


def push_system(record: dict[str, Any]) -> None:
    """Append to system buffer + broadcast to streaming subscribers."""
    global _SYSLOG_COUNTER
    with _SYSLOG_LOCK:
        _SYSLOG_COUNTER += 1
        rec = {"id": _SYSLOG_COUNTER, **record}
        _SYSLOG_BUFFER.append(rec)
    for q in list(_SUBSCRIBERS):
        try:
            q.put_nowait(rec)
        except asyncio.QueueFull:
            pass


def get_system_logs(limit: int = 200, event_prefix: str | None = None) -> list[dict[str, Any]]:
    with _SYSLOG_LOCK:
        items = list(_SYSLOG_BUFFER)
    items.reverse()
    if event_prefix:
        items = [r for r in items if str(r.get("event", "")).startswith(event_prefix)]
    return items[:limit]


def clear_system_logs() -> None:
    with _SYSLOG_LOCK:
        _SYSLOG_BUFFER.clear()


async def subscribe() -> AsyncIterator[dict[str, Any]]:
    """Async iterator yielding new system log records as they arrive.

    Replays the current buffer at start (oldest-first), then streams new
    entries until the caller cancels.
    """
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=500)
    with _SYSLOG_LOCK:
        for record in list(_SYSLOG_BUFFER):
            try:
                queue.put_nowait(record)
            except asyncio.QueueFull:
                break
    _SUBSCRIBERS.add(queue)
    try:
        while True:
            item = await queue.get()
            yield item
    finally:
        _SUBSCRIBERS.discard(queue)
