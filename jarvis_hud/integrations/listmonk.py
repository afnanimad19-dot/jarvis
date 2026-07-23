"""Minimal listmonk client (https://listmonk.app) — email/newsletter server.

listmonk is a separate self-hosted app (usually run with Docker). Once you
have it running, set:
    LISTMONK_URL=http://localhost:9000
    LISTMONK_USER=api_user
    LISTMONK_TOKEN=...   (listmonk Admin -> Users -> API user token)

This client is intentionally small: add a subscriber, send a transactional
email. It is NOT wired into the chat brain as an autonomous tool — email
sending stays a deliberate, owner-approved action.
"""

import os

import httpx


def is_configured() -> bool:
    return bool(os.environ.get("LISTMONK_URL") and os.environ.get("LISTMONK_TOKEN"))


def _client() -> httpx.Client:
    base = os.environ["LISTMONK_URL"].rstrip("/")
    auth = (os.environ.get("LISTMONK_USER", "api"), os.environ["LISTMONK_TOKEN"])
    return httpx.Client(base_url=base, auth=auth, timeout=30)


def add_subscriber(email: str, name: str = "", list_ids: list[int] | None = None) -> dict:
    with _client() as client:
        resp = client.post(
            "/api/subscribers",
            json={
                "email": email,
                "name": name or email,
                "status": "enabled",
                "lists": list_ids or [],
            },
        )
        resp.raise_for_status()
        return resp.json()


def send_transactional(template_id: int, to_email: str, data: dict | None = None) -> dict:
    with _client() as client:
        resp = client.post(
            "/api/tx",
            json={"subscriber_email": to_email, "template_id": template_id, "data": data or {}},
        )
        resp.raise_for_status()
        return resp.json()
