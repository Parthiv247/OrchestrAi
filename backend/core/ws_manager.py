"""
Shared WebSocket connection manager — imported by main.py (to register /ws endpoint)
and by route modules (to broadcast events) without circular imports.
"""
import asyncio
import json
import logging
from datetime import datetime

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WSManager:
    """Manages WebSocket connections and broadcasts events."""

    def __init__(self):
        self.active: list[WebSocket] = []
        # The running event loop captured at server startup (set by main.py)
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Called once at server startup to capture the running loop."""
        self._loop = loop

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, event_type: str, data: dict):
        msg = json.dumps({"type": event_type, "data": data, "ts": datetime.utcnow().isoformat()})
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_pipeline_event(self, pipeline_id: str, status: str, extra: dict = None):
        await self.broadcast("pipeline_status", {
            "pipeline_id": pipeline_id,
            "status": status,
            **(extra or {}),
        })

    async def broadcast_incident_event(self, incident_id: str, status: str, extra: dict = None):
        await self.broadcast("incident_update", {
            "incident_id": incident_id,
            "status": status,
            **(extra or {}),
        })

    def broadcast_incident_threadsafe(self, incident_id: str, status: str, extra: dict = None):
        """
        Thread-safe variant for calling from sync background tasks that run
        outside the main event loop (e.g. healing background threads).
        Requires set_loop() to have been called at startup.
        """
        if self._loop is None or not self._loop.is_running():
            logger.warning("WS broadcast skipped — no running event loop captured")
            return
        asyncio.run_coroutine_threadsafe(
            self.broadcast_incident_event(incident_id, status, extra),
            self._loop,
        )


# Singleton — import this everywhere
ws_manager = WSManager()
