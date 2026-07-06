"""User notification target API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from cptr.utils.notifications import (
    NotificationError,
    create_target,
    delete_target,
    get_bot_options,
    list_targets,
    test_target,
    update_target,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class TargetPayload(BaseModel):
    id: str | None = None
    type: str | None = None
    enabled: bool | None = None
    events: list[str] | None = None
    delivery: str | None = None
    config: dict | None = None


def _user_id(request: Request) -> str:
    auth = getattr(request.state, "auth", None)
    if not auth or not auth.user_id:
        raise HTTPException(401, "authentication required")
    return auth.user_id


def _payload(body: TargetPayload) -> dict:
    if hasattr(body, "model_dump"):
        return body.model_dump(exclude_unset=True)
    return body.dict(exclude_unset=True)


def _error(exc: NotificationError) -> HTTPException:
    message = str(exc)
    status = 404 if "not found" in message else 400
    return HTTPException(status, message)


@router.get("/targets")
async def api_list_targets(request: Request):
    return {"targets": await list_targets(_user_id(request))}


@router.post("/targets")
async def api_create_target(request: Request, body: TargetPayload):
    try:
        return await create_target(_user_id(request), _payload(body))
    except NotificationError as exc:
        raise _error(exc) from exc


@router.put("/targets/{target_id}")
async def api_update_target(request: Request, target_id: str, body: TargetPayload):
    try:
        return await update_target(_user_id(request), target_id, _payload(body))
    except NotificationError as exc:
        raise _error(exc) from exc


@router.delete("/targets/{target_id}")
async def api_delete_target(request: Request, target_id: str):
    ok = await delete_target(_user_id(request), target_id)
    if not ok:
        raise HTTPException(404, "notification target not found")
    return {"ok": True}


@router.post("/targets/{target_id}/test")
async def api_test_target(request: Request, target_id: str):
    try:
        return await test_target(_user_id(request), target_id)
    except NotificationError as exc:
        raise _error(exc) from exc


@router.get("/bot-options")
async def api_bot_options(request: Request):
    return {
        "bots": await get_bot_options(
            _user_id(request),
            bot_manager=getattr(request.app.state, "bot_manager", None),
        )
    }
