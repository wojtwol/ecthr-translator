"""WebSocket endpoints for real-time updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Connection manager to handle multiple WebSocket connections
class ConnectionManager:
    def __init__(self):
        # Map of document_id -> set of websocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, document_id: str):
        """Accept a new WebSocket connection for a document."""
        await websocket.accept()
        if document_id not in self.active_connections:
            self.active_connections[document_id] = set()
        self.active_connections[document_id].add(websocket)
        logger.info(f"WebSocket connected for document {document_id}")

    def disconnect(self, websocket: WebSocket, document_id: str):
        """Remove a WebSocket connection."""
        if document_id in self.active_connections:
            self.active_connections[document_id].discard(websocket)
            if not self.active_connections[document_id]:
                del self.active_connections[document_id]
        logger.info(f"WebSocket disconnected for document {document_id}")

    async def send_message(self, message: dict, document_id: str):
        """Send a message to all connections for a document."""
        if document_id not in self.active_connections:
            return

        message_text = json.dumps(message)
        disconnected = set()

        for connection in self.active_connections[document_id]:
            try:
                await connection.send_text(message_text)
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                disconnected.add(connection)

        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection, document_id)

    async def broadcast_progress(
        self,
        document_id: str,
        stage: str,
        progress: float,
        message: str = None,
    ):
        """Broadcast progress update for a document."""
        await self.send_message(
            {
                "type": "progress",
                "stage": stage,
                "progress": progress,
                "message": message,
            },
            document_id,
        )

    async def broadcast_term_update(
        self,
        document_id: str,
        term_id: str,
        term_data: dict,
    ):
        """Broadcast term update for a document."""
        await self.send_message(
            {
                "type": "term_update",
                "term_id": term_id,
                "term": term_data,
            },
            document_id,
        )

    async def broadcast_translation_complete(
        self,
        document_id: str,
        translation_id: str,
    ):
        """Broadcast translation completion."""
        logger.info(f"Broadcasting translation_complete for document {document_id}, job {translation_id}")
        await self.send_message(
            {
                "type": "translation_complete",
                "translation_id": translation_id,
            },
            document_id,
        )
        logger.info(f"translation_complete message sent for document {document_id}")

    async def broadcast_error(
        self,
        document_id: str,
        error: str,
    ):
        """Broadcast error message."""
        await self.send_message(
            {
                "type": "error",
                "error": error,
            },
            document_id,
        )


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws/{document_id}")
async def websocket_endpoint(websocket: WebSocket, document_id: str):
    """
    WebSocket endpoint for real-time updates.

    Client will receive JSON messages with types:
    - progress: { type, stage, progress, message }
    - term_update: { type, term_id, term }
    - translation_complete: { type, translation_id }
    - error: { type, error }
    """
    await manager.connect(websocket, document_id)

    # Server-side keepalive task
    async def keepalive():
        """Send keepalive pings to prevent Render timeout (55s)."""
        try:
            while True:
                await asyncio.sleep(20)  # Ping every 20s
                try:
                    await websocket.send_text("keepalive")
                except:
                    break
        except asyncio.CancelledError:
            pass

    keepalive_task = asyncio.create_task(keepalive())

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "document_id": document_id,
        })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                # Handle ping messages to keep connection alive
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break

    finally:
        keepalive_task.cancel()
        manager.disconnect(websocket, document_id)


# Helper function to get the manager instance
def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    return manager
