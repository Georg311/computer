"""SearXNG search provider.

https://docs.searxng.org/dev/search_api.html
Queries a configured SearXNG instance's JSON API.
"""

from __future__ import annotations

import httpx


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _score(item: dict[str, object]) -> float:
    try:
        return float(item.get("score") or 0)
    except (TypeError, ValueError):
        return 0


async def search(query: str, base_url: str, count: int = 5) -> str:
    """Search using a self-hosted SearXNG instance."""
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(
            f"{base_url.rstrip('/')}/search",
            params={"q": query, "format": "json"},
            headers={"User-Agent": "Mozilla/5.0 (compatible; cptr/1.0)"},
        )
        resp.raise_for_status()
        data = resp.json()

    parts = []

    for answer in data.get("answers") or []:
        answer_text = _text(answer)
        if answer_text:
            parts.append(f"> {answer_text}")

    for box in (data.get("infoboxes") or [])[:count]:
        title = _text(box.get("infobox") or box.get("title"))
        content = _text(box.get("content"))
        attributes = []
        for attr in box.get("attributes") or []:
            label = _text(attr.get("label"))
            value = _text(attr.get("value"))
            if label and value:
                attributes.append(f"{label}: {value}")

        box_parts = []
        if title:
            box_parts.append(f"**Infobox - {title}**")
        if content:
            box_parts.append(content)
        box_parts.extend(attributes)
        if box_parts:
            parts.append("\n".join(box_parts))

    results = sorted(data.get("results") or [], key=_score, reverse=True)
    for item in results[:count]:
        title = _text(item.get("title"))
        url = _text(item.get("url"))
        content = _text(item.get("content"))
        result_parts = []
        if title:
            result_parts.append(f"**{title}**")
        if url:
            result_parts.append(url)
        if content:
            result_parts.append(content)
        if result_parts:
            parts.append("\n".join(result_parts))

    suggestions = [_text(item) for item in data.get("suggestions") or []]
    suggestions = [item for item in suggestions if item]
    if suggestions:
        parts.append(f"Suggestions: {', '.join(suggestions)}")

    return "\n\n".join(parts) if parts else "No results found."
