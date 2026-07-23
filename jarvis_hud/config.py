"""Environment-driven configuration for the JARVIS HUD module."""

import os
from dataclasses import dataclass, field

try:  # optional: load jarvis_hud/.env if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    # Identity
    bot_name: str = field(default_factory=lambda: os.environ.get("JARVIS_BOT_NAME", "JARVIS"))
    owner_name: str = field(default_factory=lambda: os.environ.get("JARVIS_OWNER_NAME", "Boss"))

    # Camera (Iriun usually registers as an extra webcam — try 0, 1, 2)
    camera_index: int = field(default_factory=lambda: _int("JARVIS_CAMERA_INDEX", 0))
    flip_camera: bool = field(default_factory=lambda: _bool("JARVIS_FLIP_CAMERA", True))
    frame_width: int = field(default_factory=lambda: _int("JARVIS_FRAME_WIDTH", 640))
    stream_fps: int = field(default_factory=lambda: _int("JARVIS_STREAM_FPS", 15))
    jpeg_quality: int = field(default_factory=lambda: _int("JARVIS_JPEG_QUALITY", 70))

    # Tracking
    max_hands: int = field(default_factory=lambda: _int("JARVIS_MAX_HANDS", 2))
    enable_face: bool = field(default_factory=lambda: _bool("JARVIS_ENABLE_FACE", True))
    enable_objects: bool = field(default_factory=lambda: _bool("JARVIS_ENABLE_OBJECTS", False))

    # Brain (Anthropic). ANTHROPIC_API_KEY is read by the SDK itself.
    model: str = field(default_factory=lambda: os.environ.get("JARVIS_MODEL", "claude-fable-5"))
    fallback_model: str = field(
        default_factory=lambda: os.environ.get("JARVIS_FALLBACK_MODEL", "claude-opus-4-8")
    )
    max_tokens: int = field(default_factory=lambda: _int("JARVIS_MAX_TOKENS", 4096))

    # Voice (ElevenLabs) — optional
    elevenlabs_api_key: str = field(
        default_factory=lambda: os.environ.get("ELEVENLABS_API_KEY", "")
    )
    elevenlabs_voice_id: str = field(
        default_factory=lambda: os.environ.get("ELEVENLABS_VOICE_ID", "")
    )
    elevenlabs_model_id: str = field(
        default_factory=lambda: os.environ.get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")
    )

    # Server
    host: str = field(default_factory=lambda: os.environ.get("JARVIS_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _int("JARVIS_PORT", 8765))


settings = Settings()
