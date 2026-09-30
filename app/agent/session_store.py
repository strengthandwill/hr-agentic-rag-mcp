"""In-memory per-session conversation history.

A free-tier single-process deployment does not need a persisted session store; history resets
on process restart, which is acceptable for this demo (and is documented in deployed.md).
"""
from __future__ import annotations

import threading

_lock = threading.Lock()
_sessions: dict[str, list[dict]] = {}

MAX_HISTORY_MESSAGES = 40


def get_history(session_id: str) -> list[dict]:
    with _lock:
        return list(_sessions.get(session_id, []))


def set_history(session_id: str, messages: list[dict]) -> None:
    with _lock:
        _sessions[session_id] = messages[-MAX_HISTORY_MESSAGES:]


def reset(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)
