from fastapi import WebSocket
from typing import List, Dict

class ConnectionManager:
    def __init__(self):
        self.active_guards: List[WebSocket] = []
        self.active_residents: Dict[int, List[WebSocket]] = {}

    async def connect_guard(self, websocket: WebSocket):
        await websocket.accept()
        self.active_guards.append(websocket)

    def disconnect_guard(self, websocket: WebSocket):
        if websocket in self.active_guards:
            self.active_guards.remove(websocket)

    async def connect_resident(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_residents:
            self.active_residents[user_id] = []
        self.active_residents[user_id].append(websocket)

    def disconnect_resident(self, user_id: int, websocket: WebSocket):
        if user_id in self.active_residents and websocket in self.active_residents[user_id]:
            self.active_residents[user_id].remove(websocket)

    async def send_gate_alert_to_resident(self, user_id: int, payload: dict):
        if user_id in self.active_residents:
            for connection in self.active_residents[user_id]:
                try:
                    await connection.send_json(payload)
                except Exception:
                    pass

    async def broadcast_action_to_guards(self, payload: dict):
        for connection in self.active_guards:
            try:
                await connection.send_json(payload)
            except Exception:
                pass

manager = ConnectionManager()
