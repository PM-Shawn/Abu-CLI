"""Web search tool — lightweight search via DuckDuckGo."""

from __future__ import annotations

import asyncio
import urllib.parse
import json
from typing import Optional

from agentx.tools.decorator import tool


@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo. Returns titles, URLs and snippets.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return (default 5).
    """
    try:
        # Use DuckDuckGo HTML endpoint (no API key needed)
        encoded = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"

        proc = await asyncio.create_subprocess_exec(
            "curl", "-s", "-L", "--max-time", "15", "--connect-timeout", "5",
            "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
        except asyncio.TimeoutError:
            proc.kill()
            return f"Search timed out for: {query}"

        if proc.returncode != 0:
            return f"Search failed (curl error {proc.returncode})"

        html = stdout.decode("utf-8", errors="replace")
        results = _parse_ddg_html(html, max_results)

        if not results:
            return f"No results found for: {query}"

        output = []
        for i, r in enumerate(results, 1):
            output.append(f"{i}. {r['title']}")
            output.append(f"   {r['url']}")
            if r.get("snippet"):
                output.append(f"   {r['snippet']}")
            output.append("")

        return "\n".join(output)

    except Exception as e:
        return f"Search error: {e}"


def _parse_ddg_html(html: str, max_results: int) -> list[dict]:
    """Parse DuckDuckGo HTML results (simple regex-based parser)."""
    import re

    results = []

    # Find result blocks: class="result__a" for title+url, class="result__snippet" for snippet
    # Pattern for links
    link_pattern = re.compile(
        r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    snippet_pattern = re.compile(
        r'class="result__snippet"[^>]*>(.*?)</(?:td|div|span)>',
        re.DOTALL,
    )

    links = link_pattern.findall(html)
    snippets = snippet_pattern.findall(html)

    for i, (url, title) in enumerate(links[:max_results]):
        # Clean HTML tags from title
        title = re.sub(r"<[^>]+>", "", title).strip()
        # Decode DuckDuckGo redirect URL
        if "uddg=" in url:
            match = re.search(r"uddg=([^&]+)", url)
            if match:
                url = urllib.parse.unquote(match.group(1))

        snippet = ""
        if i < len(snippets):
            snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()

        if title and url:
            results.append({
                "title": title,
                "url": url,
                "snippet": snippet,
            })

    return results
