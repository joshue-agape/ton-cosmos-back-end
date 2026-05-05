from fastapi import WebSocket
from typing import List

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, WebSocket] = {}

    async def connect(self, stripe_session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[stripe_session_id] = websocket

    def disconnect(self, stripe_session_id: str):
        if stripe_session_id in self.active_connections:
            del self.active_connections[stripe_session_id]

    async def send_update(self, stripe_session_id: str, message: dict):
        if stripe_session_id in self.active_connections:
            await self.active_connections[stripe_session_id].send_json(message)

manager = ConnectionManager()