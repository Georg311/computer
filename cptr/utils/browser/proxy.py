"""In-memory sessions and response rewriting for the Browser proxy tab."""

from __future__ import annotations

import asyncio
import html
import re
import uuid
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import httpx


_URL_ATTRIBUTES = {
    "action",
    "background",
    "cite",
    "data",
    "formaction",
    "href",
    "poster",
    "src",
}
_SKIP_SCHEMES = ("data:", "javascript:", "mailto:", "tel:", "about:", "blob:")


@dataclass
class BrowserSession:
    session_id: str
    owner: str
    url: str = ""
    title: str = ""
    origin: str = ""
    mode: str = "proxy"
    status: str = "ready"
    device_profile: dict = field(default_factory=dict)
    device_mode: str = "auto"
    mobile_viewport: tuple[int, int] | None = None
    quality_preset: str = "balanced"
    resolved_quality: dict = field(default_factory=dict)


@dataclass
class BrowserProfile:
    client: httpx.AsyncClient


class BrowserProxyManager:
    """Owns ephemeral Browser tab sessions and per-user upstream cookie jars."""

    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}
        self._profiles: dict[str, BrowserProfile] = {}
        self._lock = asyncio.Lock()

    async def create(self, owner: str) -> BrowserSession:
        session = BrowserSession(uuid.uuid4().hex, owner)
        async with self._lock:
            self._sessions[session.session_id] = session
            self._profile(owner)
        return session

    async def close(self, session_id: str, owner: str) -> bool:
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session or session.owner != owner:
                return False
            self._sessions.pop(session_id, None)
            return True

    def ids(self, owner: str) -> list[str]:
        return [
            session_id for session_id, session in self._sessions.items() if session.owner == owner
        ]

    def session(self, session_id: str, owner: str) -> BrowserSession | None:
        session = self._sessions.get(session_id)
        return session if session and session.owner == owner else None

    async def update(
        self, session_id: str, owner: str, *, url: str | None = None, title: str | None = None
    ) -> BrowserSession | None:
        async with self._lock:
            session = self.session(session_id, owner)
            if session is None:
                return None
            if url is not None:
                session.url = url
                parsed = urlsplit(url)
                session.origin = (
                    f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
                )
            if title is not None:
                session.title = title
            return session

    def client(self, session_id: str, owner: str) -> httpx.AsyncClient | None:
        session = self.session(session_id, owner)
        return self._profile(session.owner).client if session else None

    def _profile(self, owner: str) -> BrowserProfile:
        profile = self._profiles.get(owner)
        if profile is None:
            profile = BrowserProfile(
                httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=httpx.Timeout(60.0, connect=10.0),
                    limits=httpx.Limits(max_connections=30),
                )
            )
            self._profiles[owner] = profile
        return profile

    async def close_all(self) -> None:
        clients = [profile.client for profile in self._profiles.values()]
        self._sessions.clear()
        self._profiles.clear()
        await asyncio.gather(*(client.aclose() for client in clients), return_exceptions=True)


def proxy_path(session_id: str, url: str) -> str:
    """Return the same-origin URL used by the Browser iframe for an upstream URL."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Only HTTP(S) URLs can be opened in Browser")
    host = quote(parsed.netloc, safe=":[]")
    path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
    query = f"?{parsed.query}" if parsed.query else ""
    fragment = f"#{parsed.fragment}" if parsed.fragment else ""
    return f"/api/browser/frame/{session_id}/{parsed.scheme}/{host}{path}{query}{fragment}"


def target_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Only HTTP(S) URLs can be opened in Browser")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


def resource_path(session_id: str, url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path or "/"
    return f"/api/browser/resources/{session_id}{path}" + (
        f"?{parsed.query}" if parsed.query else ""
    )


def rewrite_url(value: str, base_url: str, session_id: str) -> str:
    value = value.strip()
    if not value or value.startswith("#") or value.lower().startswith(_SKIP_SCHEMES):
        return value
    try:
        url = urljoin(base_url, value)
        return proxy_path(session_id, url)
    except ValueError:
        return value


def _rewrite_srcset(value: str, base_url: str, session_id: str) -> str:
    parts = []
    for item in value.split(","):
        url, *descriptor = item.strip().split(maxsplit=1)
        parts.append(" ".join([rewrite_url(url, base_url, session_id), *descriptor]))
    return ", ".join(parts)


class _HtmlRewriter(HTMLParser):
    def __init__(self, base_url: str, session_id: str) -> None:
        super().__init__(convert_charrefs=False)
        self.base_url = base_url
        self.session_id = session_id
        self.output: list[str] = []

    def handle_decl(self, decl: str) -> None:
        self.output.append(f"<!{decl}>")

    def handle_comment(self, data: str) -> None:
        self.output.append(f"<!--{data}-->")

    def handle_data(self, data: str) -> None:
        self.output.append(data)

    def handle_entityref(self, name: str) -> None:
        self.output.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.output.append(f"&#{name};")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag(tag, attrs, close=True)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag(tag, attrs, close=False)

    def _tag(self, tag: str, attrs: list[tuple[str, str | None]], close: bool) -> None:
        rewritten: list[tuple[str, str | None]] = []
        for key, value in attrs:
            lower = key.lower()
            if lower == "integrity":
                continue
            if value and lower in _URL_ATTRIBUTES:
                value = rewrite_url(value, self.base_url, self.session_id)
            elif value and lower == "srcset":
                value = _rewrite_srcset(value, self.base_url, self.session_id)
            elif tag.lower() == "meta" and lower == "content":
                value = re.sub(
                    r"(?i)(url\s*=\s*)([^;]+)",
                    lambda match: (
                        match.group(1)
                        + rewrite_url(match.group(2).strip(), self.base_url, self.session_id)
                    ),
                    value,
                )
            rewritten.append((key, value))
        attrs_text = "".join(
            f" {key}" if value is None else f' {key}="{html.escape(value, quote=True)}"'
            for key, value in rewritten
        )
        self.output.append(f"<{tag}{attrs_text}{' /' if close else ''}>")

    def handle_endtag(self, tag: str) -> None:
        self.output.append(f"</{tag}>")


def rewrite_html(content: str, base_url: str, session_id: str, final_url: str) -> str:
    parser = _HtmlRewriter(base_url, session_id)
    parser.feed(content)
    parser.close()
    runtime = (
        f"<script>window.__cptrBrowser={{session:{session_id!r},url:{final_url!r}}};</script>"
        '<script src="/api/browser/runtime.js"></script>'
    )
    rendered = "".join(parser.output)
    if urlsplit(final_url).hostname in {"localhost", "127.0.0.1", "::1"}:
        rendered = rewrite_javascript(rendered, final_url, session_id)
    if re.search(r"<head(?:\s[^>]*)?>", rendered, re.I):
        return re.sub(r"(<head(?:\s[^>]*)?>)", r"\1" + runtime, rendered, count=1, flags=re.I)
    return runtime + rendered


def rewrite_css(content: str, base_url: str, session_id: str) -> str:
    def replace_url(match: re.Match[str]) -> str:
        quote, value = match.group(1), match.group(2)
        return f"url({quote}{rewrite_url(value, base_url, session_id)}{quote})"

    content = re.sub(r"url\(\s*(['\"]?)([^'\")]+)\1\s*\)", replace_url, content, flags=re.I)
    return re.sub(
        r"(@import\s+(?:url\()?['\"])([^'\"]+)",
        lambda match: match.group(1) + rewrite_url(match.group(2), base_url, session_id),
        content,
        flags=re.I,
    )


def rewrite_javascript(content: str, base_url: str, session_id: str) -> str:
    """Rewrite root-relative ES module imports used by local dev servers."""
    return re.sub(
        r"((?:from\s*|import\s*\(\s*|import\s*)['\"])(/[^'\"]+)",
        lambda match: match.group(1) + rewrite_url(match.group(2), base_url, session_id),
        content,
    )


manager = BrowserProxyManager()
