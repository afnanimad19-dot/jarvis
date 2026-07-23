"""LLM provider abstraction.

Two providers:
- "anthropic"          — Claude via the official Anthropic SDK (Fable 5 with
                         server-side fallback to Opus 4.8).
- "openai_compatible"  — any OpenAI-compatible endpoint: OpenRouter
                         (https://openrouter.ai/api/v1) or a local OmniRoute
                         gateway (http://localhost:20128/v1).

History format is provider-neutral:
    {"role": "user"|"assistant", "content": [part, ...]}
    part = {"type": "text", "text": str}
         | {"type": "image_jpeg_b64", "data": str}
"""

from .config import settings

FALLBACK_BETA = "server-side-fallback-2026-06-01"


class LLMError(RuntimeError):
    pass


class AnthropicProvider:
    name = "anthropic"

    def __init__(self):
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.Anthropic()

    def chat(self, system: str, history: list) -> str:
        messages = [
            {"role": turn["role"], "content": self._convert(turn["content"])}
            for turn in history
        ]
        try:
            response = self._client.beta.messages.create(
                model=settings.model,
                max_tokens=settings.max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                betas=[FALLBACK_BETA],
                fallbacks=[{"model": settings.fallback_model}],
                messages=messages,
            )
        except self._anthropic.APIStatusError as exc:
            raise LLMError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
        except self._anthropic.APIConnectionError as exc:
            raise LLMError("Cannot reach the Anthropic API (network error).") from exc

        if response.stop_reason == "refusal":
            return "I must decline that request."
        reply = "".join(b.text for b in response.content if b.type == "text")
        return reply.strip()

    @staticmethod
    def _convert(parts):
        out = []
        for p in parts:
            if p["type"] == "text":
                out.append({"type": "text", "text": p["text"]})
            elif p["type"] == "image_jpeg_b64":
                out.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": p["data"],
                        },
                    }
                )
        return out


class OpenAICompatibleProvider:
    """OpenRouter / OmniRoute / any OpenAI-compatible gateway."""

    name = "openai_compatible"

    def __init__(self):
        import openai

        self._openai = openai
        if not settings.llm_api_key and "localhost" not in settings.llm_base_url:
            raise LLMError(
                "No API key set. Put OPENROUTER_API_KEY (or JARVIS_LLM_API_KEY) in jarvis_hud/.env"
            )
        self._client = openai.OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "local",
        )

    def chat(self, system: str, history: list) -> str:
        messages = [{"role": "system", "content": system}]
        for turn in history:
            messages.append({"role": turn["role"], "content": self._convert(turn["content"])})
        try:
            response = self._client.chat.completions.create(
                model=settings.llm_model,
                max_tokens=settings.max_tokens,
                messages=messages,
            )
        except self._openai.APIStatusError as exc:
            detail = getattr(exc, "message", str(exc))
            raise LLMError(
                f"LLM gateway error {exc.status_code}: {detail} "
                f"(model={settings.llm_model!r}, base_url={settings.llm_base_url!r} — "
                "if 404/400, the model id may be wrong or no longer free; pick another)."
            ) from exc
        except self._openai.APIConnectionError as exc:
            raise LLMError(
                f"Cannot reach LLM gateway at {settings.llm_base_url!r}. "
                "Is OmniRoute running / is your network up?"
            ) from exc

        choice = response.choices[0] if response.choices else None
        text = (choice.message.content or "") if choice else ""
        return text.strip()

    @staticmethod
    def _convert(parts):
        # Pure-text turns collapse to a plain string (best compatibility).
        if all(p["type"] == "text" for p in parts):
            return "\n".join(p["text"] for p in parts)
        out = []
        for p in parts:
            if p["type"] == "text":
                out.append({"type": "text", "text": p["text"]})
            elif p["type"] == "image_jpeg_b64":
                out.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64," + p["data"]},
                    }
                )
        return out


def build_provider():
    choice = settings.llm_provider
    if choice == "auto":
        import os

        choice = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "openai_compatible"
    if choice == "anthropic":
        return AnthropicProvider()
    if choice == "openai_compatible":
        return OpenAICompatibleProvider()
    raise LLMError(f"Unknown JARVIS_LLM_PROVIDER: {choice!r}")
