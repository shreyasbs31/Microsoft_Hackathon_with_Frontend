"""
Per-session async lock manager.

Multiple sessions run concurrently; within a single session, turns are serialised.
"""

import asyncio
from collections import defaultdict


class SessionLockManager:
    """Manages one asyncio.Lock per session_id."""

    def __init__(self):
        self._locks: dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()  # protects _locks dict itself

    async def acquire(self, session_id: str) -> asyncio.Lock:
        """Return (and lazily create) the lock for *session_id*."""
        async with self._meta_lock:
            if session_id not in self._locks:
                self._locks[session_id] = asyncio.Lock()
            return self._locks[session_id]

    def get(self, session_id: str):
        """
        Context-manager wrapper so callers can write::

            async with lock_manager.get(session_id):
                ...
        """
        return _SessionLockContext(self, session_id)

    async def cleanup(self, session_id: str):
        """Remove the lock for a session that is no longer active."""
        async with self._meta_lock:
            self._locks.pop(session_id, None)


class _SessionLockContext:
    """Async context manager that acquires and releases a session lock."""

    def __init__(self, manager: SessionLockManager, session_id: str):
        self._manager = manager
        self._session_id = session_id
        self._lock: asyncio.Lock | None = None

    async def __aenter__(self):
        self._lock = await self._manager.acquire(self._session_id)
        await self._lock.acquire()
        return self._lock

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._lock and self._lock.locked():
            self._lock.release()
        return False


# Singleton instance used across the application
session_lock_manager = SessionLockManager()
