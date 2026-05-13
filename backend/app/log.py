"""Lightweight structured logging for streaming diagnostics.

Writes single-line JSON to stderr (captured by systemd journal in production,
so `journalctl -u wordglass-api -f` shows the live stream).

Tracks elapsed milliseconds since each request started, which is what we need
to diagnose 'why is the stream slow' — is the bottleneck in first-token from
the AI provider, in chunk-to-chunk latency, or somewhere in our pipeline?

Usage:
    rid = log_event("translate.start", text_len=120, target="zh")
    log_event("translate.first_chunk", rid=rid, ms_since_start=...)
"""

from __future__ import annotations

import json
import sys
import time
import uuid


def new_request_id() -> str:
    """Short, opaque id to correlate log lines for the same request."""
    return uuid.uuid4().hex[:8]


def now_ms() -> float:
    """Monotonic time in ms — for deltas, not wall-clock."""
    return time.monotonic() * 1000.0


def log_event(event: str, **fields) -> None:
    """Emit one log line. Writes to stderr (systemd journal) and pushes to
    the in-memory ring buffer that the /api/settings/logs/system endpoint
    exposes for the in-app log viewer.
    """
    payload = {"ts": time.time(), "event": event, **fields}
    try:
        line = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        line = f'{{"event": "{event}", "log_error": "json_fail"}}'
    print(line, file=sys.stderr, flush=True)
    try:
        from .log_buffer import push_system
        push_system(payload)
    except Exception:
        # Never break the calling code because of logging
        pass
