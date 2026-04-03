"""
WebSocket endpoint for live collaborative editing of shared notes.

Protocol (all messages are JSON strings):
  Client → Server:
    {"type": "delta",  "ops": [...]}       – Quill Delta ops produced locally
    {"type": "cursor", "index": N, "length": N} – selection change

  Server → Client (broadcast to all editors of the same note except sender):
    {"type": "init",     "presence": [...]}      – sent only to newcomer on connect
    {"type": "delta",    "ops": [...], "user_id": "..."}
    {"type": "cursor",   "index": N, "length": N, "user_id": "...", "color": "...", "name": "..."}
    {"type": "presence", "action": "join"|"leave", "user": {...}|"user_id": "..."}

Room limits: MAX_EDITORS per note.  Auth via ?token= JWT query param.
"""

import json
import logging
from collections import defaultdict

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.note_share import NoteShare
from app.models.shared_note import SharedNote
from app.models.user import User
from app.services.jwt_service import decode_access_token

router = APIRouter(tags=["collab"])
logger = logging.getLogger(__name__)

MAX_EDITORS = 10

# Assign a distinct colour to each user in a room (up to 10).
_CURSOR_COLOURS = [
    "#E53935", "#8E24AA", "#039BE5", "#00897B",
    "#43A047", "#FB8C00", "#F4511E", "#D81B60",
    "#1E88E5", "#6D4C41",
]

# note_id → {user_id: (WebSocket, user_info_dict)}
_rooms: dict[str, dict[str, tuple[WebSocket, dict]]] = defaultdict(dict)


async def _broadcast(room_id: str, message: dict, exclude: str | None = None) -> None:
    """Send a JSON message to all connections in a room except `exclude`."""
    payload = json.dumps(message)
    dead: list[str] = []
    for uid, (ws, _) in list(_rooms[room_id].items()):
        if uid == exclude:
            continue
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(uid)
    for uid in dead:
        _rooms[room_id].pop(uid, None)


@router.websocket("/ws/notes/{note_id}")
async def collab_ws(
    note_id: str,
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
) -> None:
    # ── 1. Validate JWT ──────────────────────────────────────────────────────
    try:
        user_id: str = decode_access_token(
            token,
            secret=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # ── 2. Verify user exists and has access to the note ─────────────────────
    async with AsyncSessionLocal() as db:
        user_row = await db.execute(select(User).where(User.id == user_id))
        user = user_row.scalar_one_or_none()
        if user is None:
            await websocket.close(code=4001, reason="User not found")
            return

        note_row = await db.execute(
            select(SharedNote).where(SharedNote.id == note_id)
        )
        note = note_row.scalar_one_or_none()
        if note is None:
            await websocket.close(code=4004, reason="Note not found")
            return

        # Must be owner OR an accepted collaborator.
        if note.owner_id != user_id:
            share_row = await db.execute(
                select(NoteShare).where(
                    NoteShare.note_id == note_id,
                    NoteShare.shared_with_id == user_id,
                    NoteShare.status == "accepted",
                )
            )
            if share_row.scalar_one_or_none() is None:
                await websocket.close(code=4003, reason="No access to this note")
                return

        user_name: str = user.display_name or user.email

    # ── 3. Check room capacity ────────────────────────────────────────────────
    room = _rooms[note_id]
    if len(room) >= MAX_EDITORS and user_id not in room:
        await websocket.close(code=4008, reason="Room full (max 10 editors)")
        return

    # ── 4. Accept connection and register ────────────────────────────────────
    await websocket.accept()

    existing_keys = list(room.keys())
    colour_idx = existing_keys.index(user_id) if user_id in room else len(room)
    colour = _CURSOR_COLOURS[colour_idx % len(_CURSOR_COLOURS)]
    user_info = {"id": user_id, "name": user_name, "color": colour}
    room[user_id] = (websocket, user_info)

    # ── 5. Send current presence list to newcomer ─────────────────────────────
    await websocket.send_text(json.dumps({
        "type": "init",
        "presence": [info for _, info in room.values()],
    }))

    # ── 6. Announce arrival to everyone else ─────────────────────────────────
    await _broadcast(note_id, {
        "type": "presence",
        "action": "join",
        "user": user_info,
    }, exclude=user_id)

    # ── 7. Main receive loop ──────────────────────────────────────────────────
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except ValueError:
                continue

            msg_type = msg.get("type")

            if msg_type == "delta":
                await _broadcast(note_id, {
                    "type": "delta",
                    "ops": msg.get("ops", []),
                    "user_id": user_id,
                }, exclude=user_id)

            elif msg_type == "cursor":
                await _broadcast(note_id, {
                    "type": "cursor",
                    "index": msg.get("index", 0),
                    "length": msg.get("length", 0),
                    "user_id": user_id,
                    "color": colour,
                    "name": user_name,
                }, exclude=user_id)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning(
            "collab_ws: unhandled error user=%s note=%s: %s", user_id, note_id, exc
        )
    finally:
        room.pop(user_id, None)
        if not room:
            _rooms.pop(note_id, None)
        else:
            await _broadcast(note_id, {
                "type": "presence",
                "action": "leave",
                "user_id": user_id,
            })
