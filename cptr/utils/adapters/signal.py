# -*- coding: utf-8 -*-
"""Signal adapter — uses signal-cli REST API bridge.

Requires a running signal-cli-rest-api container:
    docker run -p 8080:8080 bbernhard/signal-cli-rest-api

Token format: ``base_url|phone_number`` (pipe-separated).
Example: ``http://localhost:8080|+1234567890``

Uses polling on GET /v1/receive/{number} for inbound messages
and POST /v2/send for outbound messages.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
import re
from typing import Any, Optional
from urllib.parse import quote

import httpx

from cptr.utils.bridge import Attachment, BaseAdapter, MessageEvent, chunk_message

logger = logging.getLogger(__name__)

MAX_MESSAGE_LEN = 4096


def markdown_to_signal(text: str) -> str:
    """Convert common Markdown to Signal's native style syntax.

    Signal renders ``**bold**``, ``*italic*``, `` `monospace` ``,
    ``~strikethrough~`` and ``||spoiler||`` natively (text_mode=styled),
    so those pass through unchanged.  Markdown Signal can't render is
    reduced to plain text so nothing shows up as raw markup:

    - fenced code blocks (``` … ```) → fence markers stripped
    - ~~strikethrough~~ → ~strikethrough~
    - headings (#, ##, …) → leading hashes stripped
    - [text](url) links → "text (url)"
    """
    # Fenced code blocks: drop the fence lines, keep the content.
    text = re.sub(r"^```.*$\n?", "", text, flags=re.MULTILINE)
    # Strikethrough: ~~text~~ -> ~text~
    text = re.sub(r"~~([^~]+)~~", r"~\1~", text)
    # Headings: strip leading hashes (line-start only).
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Links: [text](url) -> text (url)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r"\1 (\2)", text)
    return text


POLL_INTERVAL = 5.0  # seconds between receive polls (long-poll with timeout=30)
RECONNECT_BASE_DELAY = 2.0
RECONNECT_MAX_DELAY = 60.0


def _ext_for_mime(mime: str) -> str:
    """Map common MIME types to file extensions."""
    mapping = {
        "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
        "image/webp": ".webp", "audio/ogg": ".ogg", "audio/mpeg": ".mp3",
        "audio/aac": ".aac", "video/mp4": ".mp4", "application/pdf": ".pdf",
    }
    return mapping.get(mime, "")


def _parse_token(token: str) -> tuple[str, str]:
    """Parse 'base_url|phone_number' format."""
    if "|" in token:
        base_url, phone = token.split("|", 1)
        return base_url.strip().rstrip("/"), phone.strip()
    raise ValueError("Signal token must be 'base_url|phone_number' (pipe-separated)")


def _signal_cli_version(data: dict[str, Any]) -> str:
    versions = data.get("versions")
    if isinstance(versions, dict):
        return str(versions.get("signal-cli", "unknown"))
    if isinstance(versions, list) and versions:
        return str(versions[-1])
    if versions:
        return str(versions)
    return "unknown"


class SignalAdapter(BaseAdapter):
    """Signal bot via signal-cli REST API bridge."""

    platform = "signal"

    def __init__(self, token: str) -> None:
        super().__init__()
        self._base_url, self._phone = _parse_token(token)
        self._http: Optional[httpx.AsyncClient] = None
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None

    # ── Lifecycle ──────────────────────────────────────────

    async def connect(self) -> bool:
        self._http = httpx.AsyncClient(timeout=60)  # Increased timeout for slow signal-cli

        # Verify by fetching account info
        try:
            resp = await self._http.get(f"{self._base_url}/v1/about")
            data = resp.json()
            # Also verify the number is registered
            resp2 = await self._http.get(
                f"{self._base_url}/v1/identities/{quote(self._phone, safe='')}"
            )
            if resp2.status_code == 404:
                raise ValueError(f"Phone number {self._phone} not registered with signal-cli")
            logger.info(
                "Signal adapter connected: %s (signal-cli %s)",
                self._phone, _signal_cli_version(data),
            )
        except httpx.ConnectError:
            logger.error("Cannot connect to signal-cli REST API at %s", self._base_url)
            await self._http.aclose()
            self._http = None
            return False
        except Exception:
            logger.exception("Signal verification failed")
            await self._http.aclose()
            self._http = None
            return False

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        return True

    async def disconnect(self) -> None:
        self._running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._http:
            await self._http.aclose()
            self._http = None

    # ── Sending ────────────────────────────────────────────

    async def send(self, chat_id: str, text: str) -> str | None:
        if not self._http:
            return None
        chunks = chunk_message(markdown_to_signal(text), MAX_MESSAGE_LEN)
        timestamp = None
        for chunk in chunks:
            try:
                resp = await self._http.post(
                    f"{self._base_url}/v2/send",
                    json={
                        "message": chunk,
                        "number": self._phone,
                        "recipients": [chat_id],
                        "text_mode": "styled",
                    },
                )
                if resp.status_code not in (200, 201):
                    logger.warning(
                        "[signal] Send failed for %s — HTTP %d: %s",
                        chat_id, resp.status_code, resp.text[:200],
                    )
                    return None
                data = resp.json()
                if isinstance(data, list):
                    # v2/send success response: [{"timestamp": "..."}]
                    if data and "timestamp" in data[0]:
                        if timestamp is None:
                            timestamp = str(data[0].get("timestamp", ""))
                    else:
                        logger.warning(
                            "[signal] Send returned unexpected list for %s — %s",
                            chat_id, json.dumps(data)[:200],
                        )
                elif isinstance(data, dict) and "error" in data:
                    # v2/send error response: {"error": "..."}
                    logger.warning(
                        "[signal] Send failed for %s — %s",
                        chat_id, str(data["error"])[:200],
                    )
            except Exception:
                logger.exception("[signal] Failed to send message to %s", chat_id)
                return None
        return timestamp

    async def edit(self, chat_id: str, message_id: str, text: str) -> None:
        """Edit a previously sent Signal message.

        signal-cli-rest-api expects edit_timestamp as an INTEGER (not string).
        The response format matches send(): [{"timestamp": "..."}] on success,
        or {"error": "..."} on failure.

        Timeout can be 10-45s depending on signal-cli load — use timeout=60.
        """
        if not self._http:
            return

        # Guard against empty/non-numeric message_id
        try:
            edit_ts = int(message_id)
        except (ValueError, TypeError):
            logger.warning(
                "[signal] Cannot parse message_id for editing %s — id='%s', skipping edit",
                chat_id, message_id,
            )
            return

        try:
            resp = await self._http.post(
                f"{self._base_url}/v2/send",
                json={
                    "message": markdown_to_signal(text)[:MAX_MESSAGE_LEN],
                    "number": self._phone,
                    "recipients": [chat_id],
                    "edit_timestamp": edit_ts,  # MUST be integer, not string!
                    "text_mode": "styled",
                },
            )
            if resp.status_code not in (200, 201):
                logger.warning(
                    "[signal] Edit failed for %s — HTTP %d: %s",
                    chat_id, resp.status_code, resp.text[:200],
                )
                return

            # Parse response body (same as send())
            data = resp.json()
            if isinstance(data, list):
                logger.debug(
                    "[signal] Edit successful for %s — new_timestamp=%s",
                    chat_id, data[0].get("timestamp"),
                )
            elif isinstance(data, dict) and "error" in data:
                logger.warning(
                    "[signal] Edit returned error for %s — %s",
                    chat_id, str(data["error"])[:200],
                )

        except httpx.ReadTimeout as e:
            # signal-cli can take 10-45s per operation; log specifically
            logger.warning(
                "[signal] Edit timed out for %s after ~60s — signal-cli slow or overloaded",
                chat_id,
            )
        except Exception:
            logger.exception("[signal] Failed to edit message to %s", chat_id)

    async def send_typing(self, chat_id: str) -> None:
        """Send typing indicator via signal-cli."""
        if not self._http:
            return
        try:
            await self._http.put(
                f"{self._base_url}/v1/typing-indicator/{quote(self._phone, safe='')}",
                json={"recipient": chat_id},
            )
        except Exception:
            pass

    # ── Polling ────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        delay = RECONNECT_BASE_DELAY
        while self._running:
            try:
                resp = await self._http.get(
                    f"{self._base_url}/v1/receive/{quote(self._phone, safe='')}",
                    params={"timeout": "30"},  # long-poll: block up to 30s for new messages
                    timeout=60,
                )
                if resp.status_code == 200:
                    messages = resp.json()
                    for msg in messages:
                        try:
                            await self._process_message(msg)
                        except Exception:
                            logger.exception("Error processing Signal message")
                delay = RECONNECT_BASE_DELAY
                await asyncio.sleep(POLL_INTERVAL)

            except asyncio.CancelledError:
                return
            except (httpx.ConnectError, httpx.ReadError, httpx.WriteError, OSError, Exception) as e:
                # Reset client to clear dead connections before retrying
                if self._http:
                    await self._http.aclose()
                self._http = httpx.AsyncClient(timeout=60)  # fresh client with higher timeout

                # httpcore.ReadError (from underlying stream) is not caught by httpx.ReadError,
                # so we catch Exception and only log network-related errors as warnings.
                if isinstance(e, (httpx.ConnectError, httpx.ReadError, httpx.WriteError, OSError)):
                    logger.warning("Signal poll network error (%s), retrying in %.0fs", type(e).__name__, delay)
                else:
                    logger.warning("Signal poll error (%s), retrying in %.0fs", type(e).__name__, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, RECONNECT_MAX_DELAY)


    async def _process_message(self, msg: dict) -> None:
        envelope = msg.get("envelope", {})
        data_message = envelope.get("dataMessage")
        if not data_message:
            # System Event (Read Receipt, Reaction, etc.) — loggen statt stumm skippen
            source = envelope.get("source", "unknown")
            event_type = envelope.get("type", "unknown")
            logger.debug("[signal] Skipping non-message event from %s (type=%s)", source, event_type)
            return


        text = (data_message.get("message") or "").strip()

        # Process attachments from signal-cli
        attachments: list[Attachment] = []
        for att in data_message.get("attachments", []):
            att_id = att.get("id")
            if not att_id:
                continue
            file_data = await self._download_attachment(att_id)
            if not file_data:
                continue
            content_type = att.get("contentType", "application/octet-stream")
            fname = att.get("filename") or f"attachment{_ext_for_mime(content_type)}"
            if content_type.startswith("image/"):
                att_type = "image"
            elif content_type.startswith("audio/"):
                att_type = "audio"
            else:
                att_type = "document"
            attachments.append(Attachment(
                type=att_type, filename=fname, data=file_data, mime_type=content_type,
            ))

        if not text and not attachments:
            return

        source = envelope.get("source", "")
        source_name = envelope.get("sourceName") or source

        # Use source number as chat_id (DM) or groupId for groups
        group_info = data_message.get("groupInfo")
        chat_id = source
        if group_info:
            group_id = group_info.get("groupId", "")
            chat_id = group_info.get("id") or (
                "group." + base64.b64encode(group_id.encode("utf-8")).decode("ascii")
                if group_id
                else source
            )

        event = MessageEvent(
            platform="signal",
            chat_id=chat_id,
            sender_id=source,
            sender_name=source_name,
            text=text,
            attachments=attachments,
        )

        if self.on_message:
            await self.on_message(event)

    async def _download_attachment(self, attachment_id: str) -> bytes | None:
        """Download an attachment from signal-cli REST API."""
        if not self._http:
            return None
        try:
            resp = await self._http.get(
                f"{self._base_url}/v1/attachments/{attachment_id}",
            )
            if resp.status_code == 200:
                return resp.content
            logger.warning("[signal] Attachment download failed: HTTP %d", resp.status_code)
        except Exception:
            logger.exception("[signal] Failed to download attachment %s", attachment_id)
        return None

    async def send_photo(self, chat_id: str, data: bytes, filename: str, caption: str = "") -> str | None:
        """Send a photo as a base64 attachment."""
        return await self._send_with_attachment(chat_id, data, filename, caption)

    async def send_document(self, chat_id: str, data: bytes, filename: str, caption: str = "") -> str | None:
        """Send a document as a base64 attachment."""
        return await self._send_with_attachment(chat_id, data, filename, caption)

    async def _send_with_attachment(
        self, chat_id: str, data: bytes, filename: str, caption: str = "",
    ) -> str | None:
        """Send a message with a base64-encoded attachment via signal-cli."""
        if not self._http:
            return None
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        try:
            resp = await self._http.post(
                f"{self._base_url}/v2/send",
                json={
                    "message": markdown_to_signal(caption or ""),
                    "number": self._phone,
                    "recipients": [chat_id],
                    "text_mode": "styled",
                    "base64_attachments": [
                        {
                            "data": base64.b64encode(data).decode("ascii"),
                            "mime_type": mime,
                            "filename": filename,
                        }
                    ],
                },
            )
            if resp.status_code not in (200, 201):
                logger.warning(
                    "[signal] Send attachment failed for %s — HTTP %d: %s",
                    chat_id, resp.status_code, resp.text[:200],
                )
                return None
            result = resp.json()
            if isinstance(result, list):
                # v2/send success: [{"timestamp": "..."}]
                if result and "timestamp" in result[0]:
                    return str(result[0].get("timestamp", ""))
                else:
                    logger.warning(
                        "[signal] Send attachment returned unexpected list for %s — %s",
                        chat_id, json.dumps(result)[:200],
                    )
            elif isinstance(result, dict) and "error" in result:
                # v2/send error response: {"error": "..."}
                logger.warning(
                    "[signal] Send attachment failed for %s — %s",
                    chat_id, str(result["error"])[:200],
                )
        except Exception:
            logger.exception("[signal] Failed to send attachment")
        return None


async def verify_token(token: str) -> dict:
    """Verify signal-cli REST API connection and phone number."""
    base_url, phone = _parse_token(token)

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{base_url}/v1/about")
            data = resp.json()
        except httpx.ConnectError:
            raise ValueError(f"Cannot connect to signal-cli at {base_url}")

        # Check phone number is registered
        resp2 = await client.get(
            f"{base_url}/v1/identities/{quote(phone, safe='')}"
        )
        if resp2.status_code == 404:
            raise ValueError(f"Phone {phone} not registered with signal-cli")

        return {
            "username": phone,
            "id": phone,
            "version": _signal_cli_version(data),
        }
