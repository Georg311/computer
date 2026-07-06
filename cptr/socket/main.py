"""Socket.IO server: creates the sio instance and registers all handlers.

Usage in app.py:
    from cptr.socket.main import sio_app
    # mount sio_app as the root ASGI app
"""

from __future__ import annotations

import socketio

from cptr.utils.config import check_access
from cptr.env import CORS_ALLOWED_ORIGINS

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=CORS_ALLOWED_ORIGINS)

# user_id → set of connected sids
_user_sids: dict[str, set[str]] = {}


@sio.on("connect")
async def on_connect(sid, environ, auth):
    token = auth.get("token") if auth else None
    if not token:
        # Try cookie fallback
        cookie_header = environ.get("HTTP_COOKIE", "")
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith("cptr_session="):
                token = part.split("=", 1)[1]
                break

    client_host = environ.get("REMOTE_ADDR", "127.0.0.1")
    user = check_access(client_host=client_host, jwt_token=token)
    if not user or not user.user_id:
        raise ConnectionRefusedError("unauthorized")

    await sio.save_session(sid, {"user_id": user.user_id})
    _user_sids.setdefault(user.user_id, set()).add(sid)


@sio.on("disconnect")
async def on_disconnect(sid):
    session = await sio.get_session(sid)
    uid = session.get("user_id")
    if uid and uid in _user_sids:
        _user_sids[uid].discard(sid)
        if not _user_sids[uid]:
            del _user_sids[uid]


async def emit_to_user(user_id: str, data: dict):
    """Send events:chat to all of a user's connected tabs/windows."""
    for sid in list(_user_sids.get(user_id, set())):
        await sio.emit("events:chat", data, to=sid)


def is_user_active(user_id: str) -> bool:
    """Return True when the user has at least one connected app session."""
    return bool(_user_sids.get(user_id))


def get_asgi_app(other_app):
    """Wrap a FastAPI/Starlette app with the Socket.IO ASGI layer."""
    return socketio.ASGIApp(sio, other_asgi_app=other_app)
