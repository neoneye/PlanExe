"""
/**
 * Author: ChatGPT gpt-5-codex
 * Date: 2025-10-27T00:00:00Z
 * PURPOSE: In-memory expiring session cache for streaming analysis handshakes.
 * SRP and DRY check: Pass - dedicated to caching payloads between POST and SSE GET without
 *                    duplicating persistence logic elsewhere.
 */
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


@dataclass
class CachedAnalysisSession:
    """Session metadata preserved between handshake and SSE connection."""

    session_id: str
    task_id: str
    model_key: str
    payload: Dict[str, Any]
    created_at: datetime
    expires_at: datetime

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        reference = now or datetime.now(timezone.utc)
        return reference >= self.expires_at


class AnalysisStreamSessionStore:
    """Thread-safe store for cached streaming analysis payloads."""

    def __init__(self, ttl_seconds: int = 30) -> None:
        self._ttl = ttl_seconds
        self._sessions: Dict[str, CachedAnalysisSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        *,
        task_id: str,
        model_key: str,
        payload: Dict[str, Any],
    ) -> CachedAnalysisSession:
        """Register a new cached session and return its metadata."""

        async with self._lock:
            self._prune_locked()
            session_id = uuid4().hex
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=self._ttl)
            cached = CachedAnalysisSession(
                session_id=session_id,
                task_id=task_id,
                model_key=model_key,
                payload=payload,
                created_at=now,
                expires_at=expires_at,
            )
            self._sessions[session_id] = cached
            return cached

    async def pop_session(
        self,
        *,
        task_id: str,
        model_key: str,
        session_id: str,
    ) -> CachedAnalysisSession:
        """Retrieve and delete the cached session if it matches the handshake."""

        async with self._lock:
            self._prune_locked()
            cached = self._sessions.pop(session_id, None)
            if not cached:
                raise KeyError("SESSION_NOT_FOUND")
            if cached.is_expired():
                raise KeyError("SESSION_EXPIRED")
            if cached.task_id != task_id or cached.model_key != model_key:
                raise KeyError("SESSION_MISMATCH")
            return cached

    def _prune_locked(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [key for key, session in self._sessions.items() if session.is_expired(now)]
        for key in expired:
            self._sessions.pop(key, None)

    async def pending_sessions(self) -> Dict[str, CachedAnalysisSession]:
        """Return a snapshot of active sessions for diagnostics/testing."""

        async with self._lock:
            self._prune_locked()
            return dict(self._sessions)
