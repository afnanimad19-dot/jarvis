"""Environment-driven configuration for the JARVIS HUD module."""

import os
from dataclasses import dataclass, field

try:  # optional: load .env files if python-dotenv is installed
    from dotenv import load_dotenv

    _here = os.path.dirname(__file__)
    # Look in jarvis_hud/.env (canonical), the repo root, and the CWD —
    # people put the file in all three places; missing files are no-ops.
    for _path in (
        os.path.join(_here, ".env"),
        os.path.join(os.path.dirname(_here), ".env"),
        ".env",
    ):
        load_dotenv(_path)
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

    # Brain provider: "auto" | "anthropic" | "openai_compatible"
    # auto = anthropic if ANTHROPIC_API_KEY is set, else openai_compatible.
    llm_provider: str = field(
        default_factory=lambda: os.environ.get("JARVIS_LLM_PROVIDER", "auto")
    )

    # Anthropic path. ANTHROPIC_API_KEY is read by the SDK itself.
    model: str = field(default_factory=lambda: os.environ.get("JARVIS_MODEL", "claude-fable-5"))
    fallback_model: str = field(
        default_factory=lambda: os.environ.get("JARVIS_FALLBACK_MODEL", "claude-opus-4-8")
    )

    # OpenAI-compatible path: OpenRouter (default) or local OmniRoute gateway
    # (http://localhost:20128/v1). Pick a VISION-capable model for scan mode.
    llm_base_url: str = field(
        default_factory=lambda: os.environ.get("JARVIS_LLM_BASE_URL", "https://openrouter.ai/api/v1")
    )
    llm_api_key: str = field(
        default_factory=lambda: os.environ.get(
            "JARVIS_LLM_API_KEY", os.environ.get("OPENROUTER_API_KEY", "")
        )
    )
    llm_model: str = field(
        default_factory=lambda: os.environ.get(
            "JARVIS_LLM_MODEL", "qwen/qwen2.5-vl-72b-instruct:free"
        )
    )

    max_tokens: int = field(default_factory=lambda: _int("JARVIS_MAX_TOKENS", 4096))

    # Gesture mouse control (pinch to click-and-drag across monitors)
    gesture_hand: str = field(
        default_factory=lambda: os.environ.get("JARVIS_GESTURE_HAND", "Right")
    )
    gesture_smoothing: float = field(
        default_factory=lambda: float(os.environ.get("JARVIS_GESTURE_SMOOTHING", "0.35"))
    )

    # Voice output: auto | elevenlabs | voxcpm | off
    tts_provider: str = field(
        default_factory=lambda: os.environ.get("JARVIS_TTS_PROVIDER", "auto")
    )
    elevenlabs_api_key: str = field(
        default_factory=lambda: os.environ.get("ELEVENLABS_API_KEY", "")
    )
    elevenlabs_voice_id: str = field(
        default_factory=lambda: os.environ.get("ELEVENLABS_VOICE_ID", "")
    )
    elevenlabs_model_id: str = field(
        default_factory=lambda: os.environ.get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")
    )
    # VoxCPM (local TTS): optional voice cloning from a short sample WAV
    voxcpm_model: str = field(
        default_factory=lambda: os.environ.get("JARVIS_VOXCPM_MODEL", "openbmb/VoxCPM-0.5B")
    )
    voxcpm_prompt_wav: str = field(
        default_factory=lambda: os.environ.get("JARVIS_VOXCPM_PROMPT_WAV", "")
    )
    voxcpm_prompt_text: str = field(
        default_factory=lambda: os.environ.get("JARVIS_VOXCPM_PROMPT_TEXT", "")
    )

    # Server
    host: str = field(default_factory=lambda: os.environ.get("JARVIS_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _int("JARVIS_PORT", 8765))


settings = Settings()
