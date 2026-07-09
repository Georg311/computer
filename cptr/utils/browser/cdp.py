"""Chrome DevTools Protocol client over WebSocket.

Connects to a running Chrome/Chromium instance via CDP and provides methods for
navigation, accessibility tree snapshots with ref IDs, clicking, typing,
screenshots, and JS evaluation. Zero external dependencies beyond websockets.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

# Ref ID prefix used in accessibility tree snapshots
_REF_PREFIX = "@e"


class CDPClient:
    """Low-level Chrome DevTools Protocol client."""

    def __init__(self, ws: Any, target_id: str) -> None:
        self._ws = ws
        self._target_id = target_id
        self._msg_id = 0
        self._ref_map: dict[str, int] = {}  # ref_id -> backend_node_id
        self._closed = False

    # ── Connection ─────────────────────────────────────────

    @classmethod
    async def connect(cls, cdp_url: str = "http://localhost:9222") -> "CDPClient":
        """Connect to a Chrome instance via CDP.

        Discovers the WebSocket debug URL from the /json/version endpoint,
        then opens a WebSocket connection to the first available page target.
        """
        import httpx

        base = cdp_url.rstrip("/")

        # Get available targets (pages/tabs)
        async with httpx.AsyncClient() as http:
            resp = await http.get(f"{base}/json/list", timeout=5)
            targets = resp.json()

        # Find a page target, or create one
        page_target = None
        for t in targets:
            if t.get("type") == "page":
                page_target = t
                break

        if not page_target:
            # Create a new tab
            async with httpx.AsyncClient() as http:
                resp = await http.put(f"{base}/json/new?about:blank", timeout=5)
                page_target = resp.json()

        ws_url = page_target["webSocketDebuggerUrl"]
        target_id = page_target["id"]

        ws = await websockets.connect(
            ws_url,
            max_size=50 * 1024 * 1024,
            ping_interval=None,
        )

        client = cls(ws, target_id)

        # Enable required domains
        await client._send("Page.enable")
        await client._send("DOM.enable")
        await client._send("Accessibility.enable")
        await client._send("Runtime.enable")

        return client

    # ── Low-level CDP messaging ────────────────────────────

    async def _send(self, method: str, params: dict | None = None) -> dict:
        """Send a CDP command and wait for the result."""
        self._msg_id += 1
        msg_id = self._msg_id
        payload = {"id": msg_id, "method": method}
        if params:
            payload["params"] = params

        try:
            await self._ws.send(json.dumps(payload))

            # Wait for matching response (skip events)
            while True:
                data = await self._recv_json()
                if data.get("id") == msg_id:
                    if "error" in data:
                        raise RuntimeError(
                            f"CDP error: {data['error'].get('message', data['error'])}"
                        )
                    return data.get("result", {})
                # Ignore events (no "id" field)
        except ConnectionClosed:
            self._closed = True
            raise

    async def _recv_json(self) -> dict:
        try:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=30)
        except ConnectionClosed:
            self._closed = True
            raise
        return json.loads(raw)

    def is_closed(self) -> bool:
        """Return whether this client or its underlying socket is closed."""
        if self._closed:
            return True

        if getattr(self._ws, "closed", False):
            self._closed = True
            return True

        state_name = getattr(getattr(self._ws, "state", None), "name", None)
        if state_name in {"CLOSING", "CLOSED"}:
            self._closed = True
            return True

        return False

    # ── Navigation ─────────────────────────────────────────

    async def navigate(self, url: str) -> dict:
        """Navigate to a URL and wait for the page to load."""
        result = await self._send("Page.navigate", {"url": url})

        # Wait for load event
        while True:
            data = await self._recv_json()
            if data.get("method") == "Page.loadEventFired":
                break

        # Small delay for DOM to settle
        await asyncio.sleep(0.5)

        # Get page title
        title_result = await self._send(
            "Runtime.evaluate", {"expression": "document.title"}
        )
        title = title_result.get("result", {}).get("value", "")

        return {"url": url, "title": title, "frame_id": result.get("frameId")}

    # ── Accessibility tree snapshot ────────────────────────

    async def snapshot(self) -> str:
        """Capture the accessibility tree and return a text representation with ref IDs.

        Interactive elements (links, buttons, inputs, etc.) are assigned ref IDs
        like @e1, @e2 that can be used with click() and type_text().
        """
        result = await self._send("Accessibility.getFullAXTree")
        nodes = result.get("nodes", [])

        self._ref_map.clear()
        ref_counter = 0
        lines: list[str] = []

        # Interactive roles that get ref IDs
        interactive_roles = {
            "link", "button", "textbox", "searchbox", "combobox",
            "checkbox", "radio", "tab", "menuitem", "option",
            "switch", "slider", "spinbutton", "textfield",
        }

        for node in nodes:
            role_data = node.get("role", {})
            role = role_data.get("value", "") if isinstance(role_data, dict) else str(role_data)
            if not role or role in ("none", "generic", "InlineTextBox", "StaticText"):
                continue

            name_data = node.get("name", {})
            name = name_data.get("value", "") if isinstance(name_data, dict) else str(name_data)
            if not name and role not in interactive_roles:
                continue

            # Build indent based on depth (simplified: flat for now)
            depth = 0
            for prop in node.get("properties", []):
                if isinstance(prop, dict) and prop.get("name") == "level":
                    depth = int(prop.get("value", {}).get("value", 0))
                    break

            indent = "  " * min(depth, 4)

            # Assign ref ID to interactive elements
            ref_label = ""
            if role.lower() in interactive_roles:
                ref_counter += 1
                ref_id = f"{_REF_PREFIX}{ref_counter}"
                backend_node_id = node.get("backendDOMNodeId")
                if backend_node_id:
                    self._ref_map[ref_id] = backend_node_id
                ref_label = f" {ref_id}"

            # Format: [role @ref] Name
            display_name = f" {name}" if name else ""
            lines.append(f"{indent}[{role}{ref_label}]{display_name}")

        if not lines:
            return "[empty page]"

        return "\n".join(lines)

    # ── Interaction ────────────────────────────────────────

    async def click(self, ref: str) -> None:
        """Click an element identified by its ref ID from the latest snapshot."""
        ref = ref.strip()
        if not ref.startswith(_REF_PREFIX):
            ref = f"{_REF_PREFIX}{ref}"

        backend_node_id = self._ref_map.get(ref)
        if not backend_node_id:
            raise ValueError(f"Unknown ref '{ref}'. Run browser_snapshot() first to get valid ref IDs.")

        # Resolve to a remote object
        result = await self._send(
            "DOM.resolveNode", {"backendNodeId": backend_node_id}
        )
        object_id = result.get("object", {}).get("objectId")
        if not object_id:
            raise RuntimeError(f"Could not resolve element for ref {ref}")

        # Scroll into view
        try:
            await self._send(
                "DOM.scrollIntoViewIfNeeded", {"backendNodeId": backend_node_id}
            )
        except RuntimeError:
            pass

        # Get box model for click coordinates
        try:
            box = await self._send(
                "DOM.getBoxModel", {"backendNodeId": backend_node_id}
            )
            content = box.get("model", {}).get("content", [])
            if len(content) >= 4:
                x = (content[0] + content[2]) / 2
                y = (content[1] + content[5]) / 2
            else:
                x, y = 0, 0
        except RuntimeError:
            # Fallback: use JS click
            await self._send(
                "Runtime.callFunctionOn",
                {"objectId": object_id, "functionDeclaration": "function() { this.click(); }"},
            )
            return

        # Dispatch mouse events
        for event_type in ("mousePressed", "mouseReleased"):
            await self._send(
                "Input.dispatchMouseEvent",
                {
                    "type": event_type,
                    "x": x,
                    "y": y,
                    "button": "left",
                    "clickCount": 1,
                },
            )

        # Wait for potential navigation
        await asyncio.sleep(0.3)

    async def type_text(self, ref: str, text: str) -> None:
        """Type text into an element identified by its ref ID."""
        # Focus the element first
        ref = ref.strip()
        if not ref.startswith(_REF_PREFIX):
            ref = f"{_REF_PREFIX}{ref}"

        backend_node_id = self._ref_map.get(ref)
        if not backend_node_id:
            raise ValueError(f"Unknown ref '{ref}'. Run browser_snapshot() first.")

        await self._send("DOM.focus", {"backendNodeId": backend_node_id})

        # Clear existing content
        await self._send(
            "Input.dispatchKeyEvent",
            {"type": "keyDown", "key": "a", "modifiers": 2},  # Ctrl+A / Cmd+A
        )
        await self._send(
            "Input.dispatchKeyEvent",
            {"type": "keyUp", "key": "a", "modifiers": 2},
        )

        # Type each character
        for char in text:
            await self._send(
                "Input.dispatchKeyEvent",
                {"type": "keyDown", "key": char, "text": char},
            )
            await self._send(
                "Input.dispatchKeyEvent",
                {"type": "keyUp", "key": char},
            )

    async def scroll(self, direction: str = "down", amount: int = 3) -> None:
        """Scroll the page. Direction: 'up' or 'down'."""
        delta_y = 300 * amount * (1 if direction == "down" else -1)
        await self._send(
            "Input.dispatchMouseEvent",
            {"type": "mouseWheel", "x": 400, "y": 400, "deltaX": 0, "deltaY": delta_y},
        )
        await asyncio.sleep(0.3)

    # ── Observation ────────────────────────────────────────

    async def screenshot(self) -> bytes:
        """Capture a screenshot of the current viewport. Returns PNG bytes."""
        result = await self._send(
            "Page.captureScreenshot", {"format": "png", "quality": 80}
        )
        return base64.b64decode(result["data"])

    async def get_text(self) -> str:
        """Extract visible text content from the page."""
        result = await self._send(
            "Runtime.evaluate",
            {"expression": "document.body?.innerText || ''"},
        )
        return result.get("result", {}).get("value", "")

    async def evaluate(self, expression: str) -> str:
        """Evaluate a JavaScript expression and return the result."""
        result = await self._send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True},
        )
        value = result.get("result", {})
        if value.get("type") == "undefined":
            return "undefined"
        return str(value.get("value", value.get("description", "")))

    # ── Lifecycle ──────────────────────────────────────────

    async def close(self) -> None:
        """Close the CDP connection."""
        if not self._closed:
            self._closed = True
            try:
                await self._ws.close()
            except Exception:
                pass
