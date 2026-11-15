"""URL content reader: fetch and convert to text.

No external dependencies beyond httpx (already in the project).
"""

from __future__ import annotations

import re

import httpx


def _html_to_text(html: str) -> str:
    """Convert HTML to readable plain text. Zero external dependencies."""
    # Remove non-content blocks
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<nav[^>]*>.*?</nav>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<footer[^>]*>.*?</footer>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<header[^>]*>.*?</header>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert semantic elements
    text = re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>", r"\n\n## \1\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"\2 (\1)", text, flags=re.IGNORECASE)
    text = re.sub(
        r"<pre[^>]*>(.*?)</pre>", r"\n```\n\1\n```\n", text, flags=re.DOTALL | re.IGNORECASE
    )
    text = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", text, flags=re.IGNORECASE)
    text = re.sub(r"<strong[^>]*>(.*?)</strong>", r"**\1**", text, flags=re.IGNORECASE)
    text = re.sub(r"<b[^>]*>(.*?)</b>", r"**\1**", text, flags=re.IGNORECASE)
    text = re.sub(r"<em[^>]*>(.*?)</em>", r"*\1*", text, flags=re.IGNORECASE)

    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode common entities
    for entity, char in [
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&#39;", "'"),
        ("&nbsp;", " "),
    ]:
        text = text.replace(entity, char)

    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


async def read_url_handler(url: str) -> str:
    """Fetch content from a URL and return as readable text.

    - HTML is converted to markdown-like text
    - JSON is returned raw
    - Other text content returned as-is
    - Capped at 80KB
    """
    if not url.startswith(("http://", "https://")):
        return "Error: URL must start with http:// or https://"

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15, read=30),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=5),
        ) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; cptr/1.0)",
                    "Accept": "text/html,application/xhtml+xml,text/plain,*/*",
                },
            )
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type or "xhtml" in content_type:
            text = _html_to_text(resp.text)
        else:
            text = resp.text

        if len(text) > 80_000:
            text = text[:80_000] + "\n\n... (truncated at 80KB)"

        return f"URL: {url}\n---\n{text}" if text.strip() else f"URL: {url}\n(empty response)"

    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} for {url}"
    except httpx.TimeoutException:
        return f"Error: request timed out for {url}"
    except Exception as e:
        return f"Error fetching {url}: {e}"
