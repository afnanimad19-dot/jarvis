"""Minimal Postiz client (https://github.com/gitroomhq/postiz-app).

Postiz is a self-hosted social media scheduler (X, LinkedIn, Instagram,
YouTube, TikTok, Mastodon, ...). Run it separately (Docker), connect your
channels in its UI, create an API key (Settings -> Public API), then set:

    POSTIZ_URL=http://localhost:5000        # your Postiz instance
    POSTIZ_API_KEY=...

Approval-first by design: JARVIS only creates DRAFTS in Postiz. You review
and hit publish in the Postiz UI yourself. Nothing goes live automatically.

Note: the public-API payload shape below follows Postiz docs at the time of
writing; if a request 400s after a Postiz update, compare with
https://docs.postiz.com/public-api and adjust.
"""

import os

import httpx


def is_configured() -> bool:
    return bool(os.environ.get("POSTIZ_URL") and os.environ.get("POSTIZ_API_KEY"))


def _client() -> httpx.Client:
    base = os.environ["POSTIZ_URL"].rstrip("/") + "/api/public/v1"
    headers = {"Authorization": os.environ["POSTIZ_API_KEY"]}
    return httpx.Client(base_url=base, headers=headers, timeout=30)


def list_channels() -> list:
    """Connected social channels (integrations)."""
    with _client() as client:
        resp = client.get("/integrations")
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("integrations", data)


def create_draft(text: str, channel_ids: list[str], date_iso: str | None = None) -> dict:
    """Create a DRAFT post on the given channels. Publish manually in Postiz."""
    if not channel_ids:
        raise ValueError("channel_ids is empty — call list_channels() first.")
    payload = {
        "type": "draft",
        "date": date_iso,
        "posts": [
            {
                "integration": {"id": channel_id},
                "value": [{"content": text}],
            }
            for channel_id in channel_ids
        ],
    }
    with _client() as client:
        resp = client.post("/posts", json=payload)
        resp.raise_for_status()
        return resp.json()
