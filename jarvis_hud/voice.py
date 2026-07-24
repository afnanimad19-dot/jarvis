"""Text-to-speech with pluggable providers.

- "elevenlabs" — hosted, needs ELEVENLABS_API_KEY + ELEVENLABS_VOICE_ID. MP3.
- "voxcpm"     — local open-source TTS (OpenBMB VoxCPM). Free, offline, can
                 clone a voice from a short sample WAV. Needs
                 `pip install voxcpm` (first run downloads the model). WAV.
- "off"        — server does no TTS; the HUD falls back to the browser voice.

JARVIS_TTS_PROVIDER=auto picks: elevenlabs if configured, else voxcpm if
installed, else off.

Note on voices: use a voice you have rights to. Your own recorded sample
(VoxCPM cloning) or ElevenLabs stock voices are fine for personal use; a
cloned celebrity/character voice is not something either service licenses.
"""

import asyncio
import io
import os
import wave

import httpx

from .config import settings

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

_voxcpm_model = None
_voxcpm_error = None


def _provider() -> str:
    choice = settings.tts_provider
    if choice != "auto":
        return choice
    if settings.elevenlabs_api_key and settings.elevenlabs_voice_id:
        return "elevenlabs"
    try:
        import voxcpm  # noqa: F401

        return "voxcpm"
    except ImportError:
        return "off"


def is_configured() -> bool:
    return _provider() != "off"


def provider_name() -> str:
    return _provider()


async def synthesize(text: str):
    """Returns (audio_bytes, mime_type) or (None, None) when unavailable."""
    provider = _provider()
    if provider == "elevenlabs":
        return await _elevenlabs(text), "audio/mpeg"
    if provider == "voxcpm":
        audio = await asyncio.to_thread(_voxcpm_synthesize, text)
        return audio, "audio/wav"
    return None, None


# -- ElevenLabs --------------------------------------------------------------


async def _elevenlabs(text: str) -> bytes:
    url = ELEVENLABS_URL.format(voice_id=settings.elevenlabs_voice_id)
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


# -- VoxCPM (local) -----------------------------------------------------------


def _voxcpm_synthesize(text: str) -> bytes:
    global _voxcpm_model, _voxcpm_error
    if _voxcpm_error:
        raise RuntimeError(_voxcpm_error)
    if _voxcpm_model is None:
        try:
            from voxcpm import VoxCPM

            _voxcpm_model = VoxCPM.from_pretrained(settings.voxcpm_model)
        except Exception as exc:  # import error, download failure, OOM…
            _voxcpm_error = f"VoxCPM unavailable: {exc} (pip install voxcpm; needs a decent CPU/GPU)"
            raise RuntimeError(_voxcpm_error) from exc

    kwargs = {}
    if settings.voxcpm_prompt_wav and os.path.exists(settings.voxcpm_prompt_wav):
        kwargs["prompt_wav_path"] = settings.voxcpm_prompt_wav
        if settings.voxcpm_prompt_text:
            kwargs["prompt_text"] = settings.voxcpm_prompt_text

    audio = _voxcpm_model.generate(text=text, **kwargs)
    return _to_wav_bytes(audio, sample_rate=16000)


def _to_wav_bytes(audio, sample_rate: int) -> bytes:
    """float array (-1..1) -> 16-bit PCM WAV, stdlib only."""
    import numpy as np

    pcm = (np.clip(np.asarray(audio, dtype="float32"), -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return buf.getvalue()
