from fastapi import WebSocket
from typing import Dict, List
import json

class ConnectionManager:
    def __init__(self):
        # trip_id -> list of websockets (пассажиры и водитель)
        self.trip_connections: Dict[int, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, trip_id: int):
        await websocket.accept()
        if trip_id not in self.trip_connections:
            self.trip_connections[trip_id] = []
        self.trip_connections[trip_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, trip_id: int):
        if trip_id in self.trip_connections:
            self.trip_connections[trip_id].remove(websocket)
            if not self.trip_connections[trip_id]:
                del self.trip_connections[trip_id]
    
    async def broadcast_to_trip(self, trip_id: int, message: dict):
        if trip_id in self.trip_connections:
            for connection in self.trip_connections[trip_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass

manager = ConnectionManager()