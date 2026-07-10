"""Optional Chrome-backed Browser tabs with H.264-over-WebSocket streaming."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import secrets
import shutil
import socket
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote, urlencode, urlsplit

import httpx
import websockets
from fastapi import WebSocket, WebSocketDisconnect

from cptr.utils.browser.launcher import find_browser

FRAME_HEADER_SIZE = 14
MAX_FRAME_SIZE = 8 * 1024 * 1024
CAPTURE_TITLE = "cptr Chrome capture source"
EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


def _target_modifiers(modifiers: int, primary: bool) -> int:
    if not primary:
        return modifiers
    return (modifiers & ~6) | (4 if sys.platform == "darwin" else 2)


def _target_key(
    key: str, code: str, virtual_key: int, location: int, primary: bool
) -> tuple[str, str, int]:
    if not primary:
        return key, code, virtual_key
    target = "Meta" if sys.platform == "darwin" else "Control"
    side = "Right" if location == 2 else "Left"
    virtual_key = (92 if side == "Right" else 91) if target == "Meta" else 17
    return target, f"{target}{side}", virtual_key


def browser_name(path: str) -> str:
    name = Path(path).name.lower()
    if "brave" in name:
        return "Brave"
    if "edge" in name or "msedge" in name:
        return "Microsoft Edge"
    if "chromium" in name:
        return "Chromium"
    return "Google Chrome"


def local_origin(fallback: str) -> str:
    """Prefer the CLI's loopback port so encoder traffic never traverses a tunnel."""
    port = os.environ.get("CPTR_PORT")
    return f"http://127.0.0.1:{port}" if port else fallback.rstrip("/")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class CDPConnection:
    """Small event-safe CDP connection used only by the Chrome viewer."""

    def __init__(self, ws: Any) -> None:
        self.ws = ws
        self.message_id = 0
        self.pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self.handlers: dict[str, list[EventHandler]] = {}
        self.send_lock = asyncio.Lock()
        self.reader = asyncio.create_task(self._read())

    @classmethod
    async def connect(cls, ws_url: str) -> "CDPConnection":
        return cls(await websockets.connect(ws_url, max_size=16 * 1024 * 1024, ping_interval=None))

    async def _read(self) -> None:
        try:
            async for raw in self.ws:
                message = json.loads(raw)
                if message_id := message.get("id"):
                    future = self.pending.pop(message_id, None)
                    if future and not future.done():
                        future.set_result(message)
                    continue
                for handler in self.handlers.get(message.get("method", ""), ()):
                    asyncio.create_task(handler(message.get("params", {})))
        except Exception as exc:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(exc)
            self.pending.clear()

    async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self.send_lock:
            self.message_id += 1
            message_id = self.message_id
            future = asyncio.get_running_loop().create_future()
            self.pending[message_id] = future
            payload: dict[str, Any] = {"id": message_id, "method": method}
            if params:
                payload["params"] = params
            await self.ws.send(json.dumps(payload))
        try:
            response = await asyncio.wait_for(future, 15)
        except BaseException:
            self.pending.pop(message_id, None)
            raise
        if error := response.get("error"):
            raise RuntimeError(error.get("message", str(error)))
        return response.get("result", {})

    def on(self, method: str, handler: EventHandler) -> None:
        self.handlers.setdefault(method, []).append(handler)

    async def close(self) -> None:
        await self.ws.close()
        self.reader.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self.reader


@dataclass
class ChromeHost:
    owner: str
    browser_path: str
    port: int
    process: asyncio.subprocess.Process
    profile: str
    browser_cdp: CDPConnection
    start_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    async def create_target(self, url: str) -> tuple[str, CDPConnection]:
        encoded = quote(url, safe="")
        async with httpx.AsyncClient() as client:
            response = await client.put(f"{self.base_url}/json/new?{encoded}", timeout=10)
            response.raise_for_status()
            target = response.json()
        return target["id"], await CDPConnection.connect(target["webSocketDebuggerUrl"])

    async def close_target(self, target_id: str) -> None:
        async with httpx.AsyncClient() as client:
            with contextlib.suppress(Exception):
                await client.get(f"{self.base_url}/json/close/{target_id}", timeout=3)

    async def close(self) -> None:
        await self.browser_cdp.close()
        if self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except asyncio.TimeoutError:
                self.process.kill()
        shutil.rmtree(self.profile, ignore_errors=True)


@dataclass(eq=False)
class ViewerPeer:
    websocket: WebSocket
    queue: asyncio.Queue[dict[str, Any] | bytes] = field(
        default_factory=lambda: asyncio.Queue(maxsize=4)
    )
    waiting_keyframe: bool = True
    visible: bool = False


@dataclass
class ChromeViewer:
    session: Any
    host: ChromeHost
    target_id: str
    target_cdp: CDPConnection
    controller_id: str
    controller_cdp: CDPConnection
    encoder_token: str
    controller_origin: str
    encoder: WebSocket | None = None
    encoder_connected: asyncio.Event = field(default_factory=asyncio.Event)
    first_keyframe: asyncio.Event = field(default_factory=asyncio.Event)
    encoder_error: str = ""
    config: dict[str, Any] | None = None
    peers: set[ViewerPeer] = field(default_factory=set)
    controller: ViewerPeer | None = None
    viewport: tuple[int, int] = (1280, 720)
    target_viewport: tuple[float, float] = (1280, 720)
    restart_attempted: bool = False


class ChromeViewerManager:
    def __init__(self) -> None:
        self.hosts: dict[str, ChromeHost] = {}
        self.viewers: dict[str, ChromeViewer] = {}
        self.lock = asyncio.Lock()

    def availability(self) -> dict[str, Any]:
        path = find_browser()
        return {
            "proxy": {"available": True},
            "chrome": {
                "available": bool(path),
                "browser_name": browser_name(path) if path else None,
                "experimental": True,
                "reason": None if path else "No compatible Chrome-family browser found",
            },
        }

    async def _host(self, owner: str) -> ChromeHost:
        if existing := self.hosts.get(owner):
            if existing.process.returncode is None:
                return existing
        browser_path = find_browser()
        if not browser_path:
            raise RuntimeError("No compatible Chrome-family browser found")
        port = _free_port()
        profile = tempfile.mkdtemp(prefix="cptr-chrome-viewer-")
        args = [
            browser_path,
            f"--remote-debugging-port={port}",
            "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--window-size=1280,800",
            f"--auto-select-tab-capture-source-by-title={CAPTURE_TITLE}",
            "about:blank",
        ]
        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        version: dict[str, Any] | None = None
        async with httpx.AsyncClient() as client:
            for _ in range(30):
                if process.returncode is not None:
                    break
                try:
                    response = await client.get(f"http://127.0.0.1:{port}/json/version", timeout=1)
                    version = response.json()
                    break
                except Exception:
                    await asyncio.sleep(0.2)
        if not version:
            process.terminate()
            shutil.rmtree(profile, ignore_errors=True)
            raise RuntimeError("Chrome started without an available graphical capture session")
        browser_cdp = await CDPConnection.connect(version["webSocketDebuggerUrl"])
        info = await browser_cdp.send("SystemInfo.getInfo")
        capabilities = info.get("gpu", {}).get("videoEncoding", [])
        # Some macOS Chrome builds expose an empty capability list even when the
        # real WebCodecs encoder succeeds, so only reject an explicit negative.
        if capabilities and not any(
            "h264" in str(item.get("profile", "")).lower() for item in capabilities
        ):
            await browser_cdp.close()
            process.terminate()
            shutil.rmtree(profile, ignore_errors=True)
            raise RuntimeError("Chrome does not report hardware H.264 encoding support")
        host = ChromeHost(owner, browser_path, port, process, profile, browser_cdp)
        self.hosts[owner] = host
        return host

    async def start(self, session: Any, origin: str) -> ChromeViewer:
        if session.session_id in self.viewers:
            return self.viewers[session.session_id]
        host = await self._host(session.owner)
        async with host.start_lock:
            marker = f"data:text/html,<title>{quote(CAPTURE_TITLE)}</title>"
            target_id, target_cdp = await host.create_target(marker)
            await target_cdp.send("Page.enable")
            await target_cdp.send("Runtime.enable")
            await target_cdp.send(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                    addEventListener('click', event => {
                      const link = event.target?.closest?.('a[href]');
                      if (link && link.target && link.target !== '_self') {
                        event.preventDefault(); location.href = link.href;
                      }
                    }, true);
                    window.open = url => { if (url) location.href = url; return null; };
                    """,
                },
            )
            await target_cdp.send(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1280, "height": 720, "deviceScaleFactor": 1, "mobile": False},
            )
            token = secrets.token_urlsafe(32)
            base = local_origin(origin)
            ws_scheme = "wss" if base.startswith("https:") else "ws"
            ws_url = f"{ws_scheme}://{urlsplit(base).netloc}/api/browser/sessions/{session.session_id}/encoder"
            fragment = urlencode({"session": session.session_id, "token": token, "ws": ws_url})
            controller_url = f"{base}/browser-encoder.html#{fragment}"
            controller_id, controller_cdp = await host.create_target(controller_url)
            await controller_cdp.send("Page.enable")
            await controller_cdp.send("Runtime.enable")
            viewer = ChromeViewer(
                session, host, target_id, target_cdp, controller_id, controller_cdp, token, base
            )
            self.viewers[session.session_id] = viewer
            self._wire_events(viewer)
            try:
                for _ in range(30):
                    ready = await controller_cdp.send(
                        "Runtime.evaluate",
                        {"expression": "typeof window.startCapture === 'function'"},
                    )
                    if ready.get("result", {}).get("value") is True:
                        break
                    await asyncio.sleep(0.1)
                await controller_cdp.send(
                    "Runtime.evaluate",
                    {
                        "expression": "window.startCapture()",
                        "userGesture": True,
                    },
                )
                await asyncio.wait_for(viewer.first_keyframe.wait(), 5)
                if viewer.encoder_error:
                    raise RuntimeError(viewer.encoder_error)
                if session.url:
                    await target_cdp.send("Page.navigate", {"url": session.url})
                else:
                    await target_cdp.send("Page.navigate", {"url": "about:blank"})
                session.status = "playing"
                await self._refresh_state(viewer)
                await self._send_encoder(viewer, {"type": "pause"})
                return viewer
            except Exception:
                self.viewers.pop(session.session_id, None)
                await target_cdp.close()
                await controller_cdp.close()
                await host.close_target(target_id)
                await host.close_target(controller_id)
                raise

    def _wire_events(self, viewer: ChromeViewer) -> None:
        async def refresh(_: dict[str, Any]) -> None:
            await self._refresh_state(viewer)

        async def dialog(_: dict[str, Any]) -> None:
            # Browser chrome is not part of tab capture, so never leave an invisible modal blocking it.
            with contextlib.suppress(Exception):
                await viewer.target_cdp.send("Page.handleJavaScriptDialog", {"accept": True})

        for method in (
            "Page.frameNavigated",
            "Page.navigatedWithinDocument",
            "Page.loadEventFired",
        ):
            viewer.target_cdp.on(method, refresh)
        viewer.target_cdp.on("Page.javascriptDialogOpening", dialog)

    async def _refresh_state(self, viewer: ChromeViewer) -> None:
        try:
            value = await viewer.target_cdp.send(
                "Runtime.evaluate",
                {
                    "expression": "({url: location.href, title: document.title})",
                    "returnByValue": True,
                },
            )
            page = value.get("result", {}).get("value", {})
            history = await viewer.target_cdp.send("Page.getNavigationHistory")
            entries = history.get("entries", [])
            index = int(history.get("currentIndex", 0))
            url = str(page.get("url", ""))
            if url.startswith(("http://", "https://")):
                viewer.session.url = url
                parsed = urlsplit(url)
                viewer.session.origin = f"{parsed.scheme}://{parsed.netloc}"
            viewer.session.title = str(page.get("title", ""))[:512]
            await self._broadcast_json(
                viewer,
                {
                    "type": "state",
                    "url": viewer.session.url,
                    "title": viewer.session.title,
                    "can_go_back": index > 0,
                    "can_go_forward": index < len(entries) - 1,
                },
            )
        except Exception:
            pass

    async def encoder_socket(self, websocket: WebSocket, session_id: str, token: str) -> None:
        viewer = self.viewers.get(session_id)
        if not viewer or not secrets.compare_digest(viewer.encoder_token, token):
            await websocket.close(code=4001, reason="unauthorized")
            return
        if viewer.encoder is not None:
            await websocket.close(code=4009, reason="encoder already connected")
            return
        await websocket.accept()
        viewer.encoder = websocket
        viewer.encoder_connected.set()
        try:
            while True:
                message = await websocket.receive()
                if message.get("text") is not None:
                    data = json.loads(message["text"])
                    if data.get("type") == "config":
                        viewer.config = data
                        await self._broadcast_json(viewer, data)
                    elif data.get("type") == "error":
                        viewer.encoder_error = str(data.get("message", "Chrome encoder failed"))
                        viewer.first_keyframe.set()
                elif message.get("bytes") is not None:
                    frame = message["bytes"]
                    if not FRAME_HEADER_SIZE <= len(frame) <= MAX_FRAME_SIZE or frame[0] != 1:
                        continue
                    if frame[1] & 1:
                        viewer.first_keyframe.set()
                    await self._broadcast_frame(viewer, frame)
                else:
                    break
        except (WebSocketDisconnect, json.JSONDecodeError):
            pass
        finally:
            if viewer.encoder is websocket:
                viewer.encoder = None
                viewer.session.status = "lost"
                await self._broadcast_json(
                    viewer,
                    {"type": "status", "status": "lost", "message": "Chrome encoder disconnected"},
                )
                if self.viewers.get(session_id) is viewer:
                    asyncio.create_task(self._restart_encoder(viewer))

    async def _restart_encoder(self, viewer: ChromeViewer) -> None:
        if viewer.restart_attempted:
            await self._fallback_to_proxy(viewer, "Chrome encoder could not reconnect")
            return
        viewer.restart_attempted = True
        try:
            async with viewer.host.start_lock:
                await viewer.controller_cdp.close()
                await viewer.host.close_target(viewer.controller_id)
                await viewer.target_cdp.send(
                    "Runtime.evaluate",
                    {"expression": f"document.title={CAPTURE_TITLE!r}"},
                )
                viewer.encoder_token = secrets.token_urlsafe(32)
                base = viewer.controller_origin
                ws_scheme = "wss" if base.startswith("https:") else "ws"
                ws_url = (
                    f"{ws_scheme}://{urlsplit(base).netloc}/api/browser/sessions/"
                    f"{viewer.session.session_id}/encoder"
                )
                fragment = urlencode(
                    {
                        "session": viewer.session.session_id,
                        "token": viewer.encoder_token,
                        "ws": ws_url,
                    }
                )
                viewer.controller_id, viewer.controller_cdp = await viewer.host.create_target(
                    f"{base}/browser-encoder.html#{fragment}"
                )
                await viewer.controller_cdp.send("Runtime.enable")
                viewer.first_keyframe.clear()
                viewer.encoder_error = ""
                for _ in range(30):
                    ready = await viewer.controller_cdp.send(
                        "Runtime.evaluate",
                        {"expression": "typeof window.startCapture === 'function'"},
                    )
                    if ready.get("result", {}).get("value") is True:
                        break
                    await asyncio.sleep(0.1)
                await viewer.controller_cdp.send(
                    "Runtime.evaluate",
                    {"expression": "window.startCapture()", "userGesture": True},
                )
                await asyncio.wait_for(viewer.first_keyframe.wait(), 5)
                if viewer.encoder_error:
                    raise RuntimeError(viewer.encoder_error)
                viewer.session.status = "playing"
                await self._broadcast_json(
                    viewer, {"type": "status", "status": "playing", "message": ""}
                )
        except Exception:
            await self._fallback_to_proxy(viewer, "Chrome encoder could not reconnect")

    async def _fallback_to_proxy(self, viewer: ChromeViewer, message: str) -> None:
        if self.viewers.get(viewer.session.session_id) is not viewer:
            return
        viewer.session.mode = "proxy"
        viewer.session.status = "ready"
        await self._broadcast_json(
            viewer,
            {"type": "status", "status": "lost", "mode": "proxy", "message": message},
        )
        await asyncio.sleep(0.1)
        await self.stop(viewer.session.session_id, viewer.session.owner)

    async def viewer_socket(self, websocket: WebSocket, viewer: ChromeViewer) -> None:
        await websocket.accept()
        peer = ViewerPeer(websocket)
        viewer.peers.add(peer)
        if viewer.controller is None:
            viewer.controller = peer
        await peer.queue.put(
            {"type": "ready", "mode": "chrome", "controller": viewer.controller is peer}
        )
        if viewer.config:
            await peer.queue.put(viewer.config)
        await self._refresh_state(viewer)
        await self._request_keyframe(viewer)

        async def write() -> None:
            while True:
                message = await peer.queue.get()
                if isinstance(message, bytes):
                    await websocket.send_bytes(message)
                else:
                    await websocket.send_json(message)

        writer = asyncio.create_task(write())
        try:
            while True:
                data = await websocket.receive_json()
                await self._viewer_message(viewer, peer, data)
        except (WebSocketDisconnect, json.JSONDecodeError):
            pass
        finally:
            writer.cancel()
            viewer.peers.discard(peer)
            if viewer.controller is peer:
                viewer.controller = next(iter(viewer.peers), None)
            await self._set_visibility(viewer, peer, False)

    async def _viewer_message(
        self, viewer: ChromeViewer, peer: ViewerPeer, data: dict[str, Any]
    ) -> None:
        kind = data.get("type")
        if kind == "visibility":
            await self._set_visibility(viewer, peer, bool(data.get("visible")))
            return
        if viewer.controller is not peer:
            return
        if kind == "viewport":
            width = max(320, min(1920, int(data.get("width", 1280))))
            height = max(240, min(1080, int(data.get("height", 720))))
            viewer.viewport = (width, height)
            await viewer.target_cdp.send(
                "Emulation.setDeviceMetricsOverride",
                {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False},
            )
            metrics = await viewer.target_cdp.send("Page.getLayoutMetrics")
            visual = metrics.get("cssVisualViewport", {})
            viewer.target_viewport = (
                float(visual.get("clientWidth", width)),
                float(visual.get("clientHeight", height)),
            )
        elif kind == "navigate":
            url = str(data.get("url", ""))
            parsed = urlsplit(url)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                await viewer.target_cdp.send("Page.navigate", {"url": url})
        elif kind in {"back", "forward"}:
            history = await viewer.target_cdp.send("Page.getNavigationHistory")
            entries = history.get("entries", [])
            index = int(history.get("currentIndex", 0)) + (-1 if kind == "back" else 1)
            if 0 <= index < len(entries):
                await viewer.target_cdp.send(
                    "Page.navigateToHistoryEntry", {"entryId": entries[index]["id"]}
                )
        elif kind == "reload":
            await viewer.target_cdp.send("Page.reload")
        elif kind == "pointer":
            await self._pointer(viewer, data)
        elif kind == "wheel":
            await self._wheel(viewer, data)
        elif kind == "key":
            event = str(data.get("event", ""))
            if event not in {"keyDown", "keyUp", "char"}:
                return
            text = str(data.get("text", ""))
            key = str(data.get("key", ""))
            code = str(data.get("code", ""))
            location = max(0, min(3, int(data.get("location", 0))))
            virtual_key = max(0, min(65535, int(data.get("windows_virtual_key_code", 0))))
            key, code, virtual_key = _target_key(
                key,
                code,
                virtual_key,
                location,
                bool(data.get("primary_modifier_key", False)),
            )
            modifiers = _target_modifiers(
                int(data.get("modifiers", 0)), bool(data.get("primary_modifier", False))
            )
            params: dict[str, Any] = {
                "type": "rawKeyDown" if event == "keyDown" and not text else event,
                "key": key,
                "code": code,
                "text": text,
                "unmodifiedText": str(data.get("unmodified_text", "")),
                "modifiers": modifiers,
                "autoRepeat": bool(data.get("auto_repeat", False)),
                "location": location,
                "isKeypad": bool(data.get("is_keypad", False)),
                "windowsVirtualKeyCode": virtual_key,
            }
            await viewer.target_cdp.send(
                "Input.dispatchKeyEvent",
                params,
            )
        elif kind == "paste":
            await viewer.target_cdp.send("Input.insertText", {"text": str(data.get("text", ""))})
        elif kind == "request_keyframe":
            await self._request_keyframe(viewer)

    async def _pointer(self, viewer: ChromeViewer, data: dict[str, Any]) -> None:
        coordinates = self._coordinates(viewer, data)
        if coordinates is None:
            return
        x, y = coordinates
        event = {"move": "mouseMoved", "down": "mousePressed", "up": "mouseReleased"}.get(
            str(data.get("event"))
        )
        if not event:
            return
        params = {
            "x": x,
            "y": y,
            "button": str(data.get("button", "none")),
            "buttons": max(0, min(7, int(data.get("buttons", 0)))),
            "clickCount": max(0, min(3, int(data.get("click_count", 0)))),
            "modifiers": int(data.get("modifiers", 0)),
            "pointerType": "mouse",
        }
        if event == "mousePressed":
            await viewer.target_cdp.send(
                "Input.dispatchMouseEvent", {**params, "type": "mouseMoved", "button": "none"}
            )
        await viewer.target_cdp.send(
            "Input.dispatchMouseEvent",
            {**params, "type": event},
        )

    async def _wheel(self, viewer: ChromeViewer, data: dict[str, Any]) -> None:
        coordinates = self._coordinates(viewer, data)
        if coordinates is None:
            return
        x, y = coordinates
        await viewer.target_cdp.send(
            "Input.dispatchMouseEvent",
            {
                "type": "mouseWheel",
                "x": x,
                "y": y,
                "deltaX": float(data.get("delta_x", 0)),
                "deltaY": float(data.get("delta_y", 0)),
                "modifiers": int(data.get("modifiers", 0)),
            },
        )

    @staticmethod
    def _coordinates(viewer: ChromeViewer, data: dict[str, Any]) -> tuple[float, float] | None:
        x, y = float(data.get("x", -1)), float(data.get("y", -1))
        if data.get("normalized"):
            if not (0 <= x <= 1 and 0 <= y <= 1):
                return None
            width, height = viewer.target_viewport
            return x * width, y * height
        width, height = viewer.viewport
        return (x, y) if 0 <= x <= width and 0 <= y <= height else None

    async def _set_visibility(self, viewer: ChromeViewer, peer: ViewerPeer, visible: bool) -> None:
        peer.visible = visible
        await self._send_encoder(
            viewer, {"type": "resume" if any(item.visible for item in viewer.peers) else "pause"}
        )
        if visible:
            await self._request_keyframe(viewer)

    async def _request_keyframe(self, viewer: ChromeViewer) -> None:
        await self._send_encoder(viewer, {"type": "keyframe"})

    async def _send_encoder(self, viewer: ChromeViewer, message: dict[str, Any]) -> None:
        if viewer.encoder:
            with contextlib.suppress(Exception):
                await viewer.encoder.send_json(message)

    async def _broadcast_json(self, viewer: ChromeViewer, message: dict[str, Any]) -> None:
        for peer in tuple(viewer.peers):
            if peer.queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    peer.queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                peer.queue.put_nowait(message)

    async def _broadcast_frame(self, viewer: ChromeViewer, frame: bytes) -> None:
        keyframe = bool(frame[1] & 1)
        for peer in tuple(viewer.peers):
            if not peer.visible or (peer.waiting_keyframe and not keyframe):
                continue
            if peer.queue.full():
                while not peer.queue.empty():
                    with contextlib.suppress(asyncio.QueueEmpty):
                        peer.queue.get_nowait()
                peer.waiting_keyframe = True
                await self._request_keyframe(viewer)
                if not keyframe:
                    continue
            if keyframe:
                peer.waiting_keyframe = False
            peer.queue.put_nowait(frame)

    async def stop(self, session_id: str, owner: str) -> bool:
        viewer = self.viewers.get(session_id)
        if not viewer or viewer.session.owner != owner:
            return False
        self.viewers.pop(session_id, None)
        for peer in tuple(viewer.peers):
            with contextlib.suppress(Exception):
                await peer.websocket.close(code=1001)
        if viewer.encoder:
            with contextlib.suppress(Exception):
                await viewer.encoder.close(code=1001)
        await viewer.target_cdp.close()
        await viewer.controller_cdp.close()
        await viewer.host.close_target(viewer.target_id)
        await viewer.host.close_target(viewer.controller_id)
        return True

    async def close_all(self) -> None:
        for viewer in tuple(self.viewers.values()):
            await self.stop(viewer.session.session_id, viewer.session.owner)
        for host in tuple(self.hosts.values()):
            await host.close()
        self.hosts.clear()


manager = ChromeViewerManager()
