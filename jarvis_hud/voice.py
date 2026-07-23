"""ElevenLabs text-to-speech. Optional — needs ELEVENLABS_API_KEY and
ELEVENLABS_VOICE_ID. Returns MP3 bytes, or None when not configured.

Note: use a voice you have rights to. ElevenLabs stock voices or your own
clones are fine for personal use; a cloned celebrity/character voice is not
something they license.
"""

import httpx

from .config import settings

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def is_configured() -> bool:
    return bool(settings.elevenlabs_api_key and settings.elevenlabs_voice_id)


async def synthesize(text: str) -> bytes | None:
    if not is_configured():
        return None
    url = API_URL.format(voice_id=settings.elevenlabs_voice_id)
    payload = {
        "text": text,
        "model_id": settings.elevenlabs_model_id,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    headers = {"xi-api-key": settings.elevenlabs_api_key, "accept": "audio/mpeg"}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.content
