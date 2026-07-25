"""Telegram messaging via a bot you own — free and official.

Setup (5 minutes, one time):
1. In Telegram, message @BotFather -> /newbot -> pick a name -> copy the TOKEN.
2. Message your new bot anything (opens the chat).
3. Get your chat id: open https://api.telegram.org/bot<TOKEN>/getUpdates
   in a browser and read "chat":{"id": 123456789 ...}.
4. In jarvis_hud/.env:
       TELEGRAM_BOT_TOKEN=123456:ABC-...
       TELEGRAM_CHAT_ID=123456789

"Jarvis, telegram: buy milk" then sends to YOUR Telegram (notes-to-self).
Other recipients must also open a chat with your bot; use their chat id.
"""

import os

import httpx


def is_configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


async def send(text: str, chat_id: str = "") -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        raise RuntimeError("Telegram not configured (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in .env).")
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text},
        )
        resp.raise_for_status()
        return resp.json()
