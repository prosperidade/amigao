import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional
import redis.asyncio as aioredis
from app.core.config import settings
from app.schemas.token import TokenPayload
from jose import jwt, JWTError
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        # Maps scoped channel key -> [WebSockets]
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.redis: aioredis.Redis | None = None
        self.pubsub: aioredis.client.PubSub | None = None
        self.listener_task: asyncio.Task | None = None

    def _scope_key(self, tenant_id: int, client_id: Optional[int] = None) -> str:
        if client_id is not None:
            return f"client:{tenant_id}:{client_id}"
        return f"tenant:{tenant_id}"

    async def connect_redis(self):
        if not self.redis:
            self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            self.pubsub = self.redis.pubsub()
            try:
                await self.pubsub.subscribe(settings.REALTIME_EVENTS_CHANNEL)
                self.listener_task = asyncio.create_task(self._listen_to_redis())
            except Exception:
                self.pubsub = None
                self.redis = None
                raise

    async def close_redis(self):
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass
            self.listener_task = None
        if self.pubsub:
            await self.pubsub.close()
            self.pubsub = None
        if self.redis:
            await self.redis.close()
            self.redis = None

    async def _listen_to_redis(self):
        if not self.pubsub:
            return
        async for message in self.pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    tenant_id = data.get("tenant_id")
                    if not tenant_id:
                        continue

                    client_id = data.get("client_id") if data.get("scope") == "client" else None
                    scope_key = self._scope_key(tenant_id, client_id)
                    if scope_key in self.active_connections:
                        for connection in self.active_connections[scope_key]:
                            await connection.send_json(data)
                except Exception as e:
                    logger.error(f"Error parsing redis message: {e}")

    async def connect(self, websocket: WebSocket, tenant_id: int, client_id: Optional[int] = None):
        await websocket.accept()
        scope_key = self._scope_key(tenant_id, client_id)
        if scope_key not in self.active_connections:
            self.active_connections[scope_key] = []
        self.active_connections[scope_key].append(websocket)

    def disconnect(self, websocket: WebSocket, tenant_id: int, client_id: Optional[int] = None):
        scope_key = self._scope_key(tenant_id, client_id)
        if scope_key in self.active_connections:
            if websocket in self.active_connections[scope_key]:
                self.active_connections[scope_key].remove(websocket)
            if not self.active_connections[scope_key]:
                del self.active_connections[scope_key]

    async def broadcast_event(
        self,
        tenant_id: int,
        event_type: str,
        payload: dict,
        client_id: Optional[int] = None,
    ):
        if not self.redis:
            await self.connect_redis()
        
        message = {
            "tenant_id": tenant_id,
            "client_id": client_id,
            "scope": "client" if client_id is not None else "tenant",
            "event": event_type,
            "payload": payload
        }
        await self.redis.publish(settings.REALTIME_EVENTS_CHANNEL, json.dumps(message))

manager = ConnectionManager()

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
        client_id = token_data.client_id
        if token_data.profile == "client_portal" and client_id is None:
            await websocket.close(code=1008)
            return
        await manager.connect(websocket, tenant_id, client_id)
        
        try:
            while True:
                # Wait for messages (can be used for pings)
                data = await websocket.receive_text()
                await websocket.send_text(f"Message text was: {data}")
        except WebSocketDisconnect:
            manager.disconnect(websocket, tenant_id, client_id)
            
    except JWTError:
        await websocket.close(code=1008)
