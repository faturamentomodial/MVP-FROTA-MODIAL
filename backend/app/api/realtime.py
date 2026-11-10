import asyncio
import time
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.security import decode_access_token
from app.services.realtime import allowed_topics, read_snapshot

router = APIRouter()


@router.websocket('/realtime')
async def realtime(websocket: WebSocket):
    origin = websocket.headers.get('origin')
    if origin and origin not in settings.allowed_origins and '*' not in settings.allowed_origins:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    queue = asyncio.Queue(maxsize=1)
    hub = websocket.app.state.realtime
    receiver = None
    try:
        # Token is never included in URLs, proxy logs, or event payloads.
        message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        payload = decode_access_token(message.get('token', ''))
        user_id = int(payload['sub'])
        expires_at = float(payload['exp'])
        if expires_at <= time.time():
            raise ValueError('Expired token')
        hub.subscribers.add(queue)  # Subscribe BEFORE reading to avoid a commit race.
        versions, users = await asyncio.to_thread(read_snapshot)
        identity = users.get(user_id)
        if not identity or not identity[1]:
            await websocket.close(code=4401)
            return
        role = identity[0]
        topics = allowed_topics(role)
        previous = {topic: versions.get(topic, '') for topic in topics}
        await websocket.send_json({'type': 'sync', 'topics': sorted(topics)})
        receiver = asyncio.create_task(websocket.receive_text())
        while True:
            update = asyncio.create_task(queue.get())
            try:
                remaining = max(0, expires_at - time.time())
                done, _ = await asyncio.wait({receiver, update}, timeout=min(20, remaining), return_when=asyncio.FIRST_COMPLETED)
                if receiver in done:
                    receiver.result()
                    break  # Protocol is server push after authentication.
                # Treat an expiration timeout as final even if the platform's wall
                # clock has coarser resolution than asyncio's monotonic timer.
                if expires_at <= time.time() or (not done and remaining <= 20):
                    await websocket.close(code=4401)
                    return
                if update in done:
                    versions, users = update.result()
                    if users.get(user_id) != identity:
                        await websocket.close(code=4401)
                        return
                    current = {topic: versions.get(topic, '') for topic in topics}
                    changed = sorted(topic for topic in topics if current[topic] != previous[topic])
                    previous = current
                    if changed:
                        await asyncio.wait_for(websocket.send_json({'type': 'invalidate', 'topics': changed}), timeout=10)
                else:
                    await asyncio.wait_for(websocket.send_json({'type': 'heartbeat'}), timeout=10)
            finally:
                update.cancel()
                with suppress(asyncio.CancelledError):
                    await update
    except (ValueError, TypeError, KeyError, AttributeError, asyncio.TimeoutError):
        with suppress(RuntimeError, WebSocketDisconnect):
            await websocket.close(code=4401)
    except WebSocketDisconnect:
        pass
    finally:
        hub.subscribers.discard(queue)
        if receiver:
            receiver.cancel()
            with suppress(asyncio.CancelledError, WebSocketDisconnect):
                await receiver
