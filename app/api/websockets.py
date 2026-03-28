import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, List
import redis.asyncio as aioredis
from app.core.config import settings
from app.api.deps import get_current_user
from app.schemas.token import TokenPayload
from jose import jwt, JWTError
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        # Maps tenant_id -> [WebSockets]
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.redis: aioredis.Redis | None = None
        self.pubsub: aioredis.client.PubSub | None = None

    async def connect_redis(self):
        if not self.redis:
            self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            self.pubsub = self.redis.pubsub()
            await self.pubsub.subscribe("amigao_events")
            asyncio.create_task(self._listen_to_redis())

    async def _listen_to_redis(self):
        if not self.pubsub:
            return
        async for message in self.pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    tenant_id = data.get("tenant_id")
                    if tenant_id and tenant_id in self.active_connections:
                        for connection in self.active_connections[tenant_id]:
                            await connection.send_json(data)
                except Exception as e:
                    logger.error(f"Error parsing redis message: {e}")

    async def connect(self, websocket: WebSocket, tenant_id: int):
        await websocket.accept()
        if tenant_id not in self.active_connections:
            self.active_connections[tenant_id] = []
        self.active_connections[tenant_id].append(websocket)

    def disconnect(self, websocket: WebSocket, tenant_id: int):
        if tenant_id in self.active_connections:
            if websocket in self.active_connections[tenant_id]:
                self.active_connections[tenant_id].remove(websocket)
            if not self.active_connections[tenant_id]:
                del self.active_connections[tenant_id]

    async def broadcast_event(self, tenant_id: int, event_type: str, payload: dict):
        if not self.redis:
            await self.connect_redis()
        
        message = {
            "tenant_id": tenant_id,
            "event": event_type,
            "payload": payload
        }
        await self.redis.publish("amigao_events", json.dumps(message))

manager = ConnectionManager()

@router.on_event("startup")
async def startup_event():
    await manager.connect_redis()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
        user_id = int(token_data.sub)
        
        # We should ideally hit the DB to get the tenant_id, but the token payload can include it eventually
        # For MVP, we extract tenant directly from DB (can't use Depends in WebSockets easily without extra auth layers)
        from app.db.session import SessionLocal
        from app.models.user import User
        db = SessionLocal()
        user = db.query(User).filter(User.id == user_id).first()
        db.close()
        
        if not user:
            await websocket.close(code=1008)
            return

        tenant_id = user.tenant_id
        await manager.connect(websocket, tenant_id)
        
        try:
            while True:
                # Wait for messages (can be used for pings)
                data = await websocket.receive_text()
                await websocket.send_text(f"Message text was: {data}")
        except WebSocketDisconnect:
            manager.disconnect(websocket, tenant_id)
            
    except JWTError:
        await websocket.close(code=1008)
