"""Web crawling via crawl4ai (https://github.com/unclecode/crawl4ai).

Fetches a URL and returns clean, LLM-friendly markdown. Used by the /crawl
console command: crawl a page, optionally have the brain answer a question
about it.

Requires:
    pip install crawl4ai
    crawl4ai-setup            # installs its Playwright browser
    JARVIS_ENABLE_CRAWL=1

Reality check: many social platforms (Instagram, VSCO, TikTok, X) aggressively
block automated crawlers and wall content behind login — public marketing
pages, blogs, docs, and product pages work far better. Respect each site's
terms; this is for your own research, not mass scraping.
"""

import os

MAX_MARKDOWN_CHARS = 24_000


def is_enabled() -> bool:
    return os.environ.get("JARVIS_ENABLE_CRAWL", "").strip().lower() in ("1", "true", "yes")


async def crawl(url: str) -> str:
    if not is_enabled():
        raise RuntimeError("Crawling disabled. Set JARVIS_ENABLE_CRAWL=1 to enable.")
    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError as exc:
        raise RuntimeError(
            "crawl4ai not installed. Run: pip install crawl4ai && crawl4ai-setup"
        ) from exc

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)

    markdown = str(getattr(result, "markdown", "") or "")
    if not markdown.strip():
        raise RuntimeError(f"Crawl of {url} returned no content (blocked or empty page?).")
    if len(markdown) > MAX_MARKDOWN_CHARS:
        markdown = markdown[:MAX_MARKDOWN_CHARS] + "\n\n[...truncated...]"
    return markdown
