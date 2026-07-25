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

import time

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
        self.last_model = settings.model

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
        # max_retries=0: the SDK's own 429 retries (2x with backoff) would sit
        # IN FRONT of our instant model-hopping — our chain is the retry.
        self._client = openai.OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "local",
            max_retries=0,
            timeout=45,
        )
        self._discovered = None  # (timestamp, all_free_ids, vision_free_ids)
        self.last_model = None

    def _discover_free_models(self):
        """All :free model ids on the gateway — the automatic fallback pool."""
        if not settings.llm_auto_fallbacks:
            return [], []
        if self._discovered and time.time() - self._discovered[0] < 600:
            return self._discovered[1], self._discovered[2]
        try:
            import httpx

            resp = httpx.get(settings.llm_base_url.rstrip("/") + "/models", timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except Exception:
            # Network hiccup: keep whatever we had; never break chat over this.
            return (self._discovered[1], self._discovered[2]) if self._discovered else ([], [])

        free, vision = [], []
        for m in data:
            mid = m.get("id", "")
            if not mid.endswith(":free"):
                continue
            if "safety" in mid or "guard" in mid:  # classifiers, not chat models
                continue
            free.append(mid)
            modalities = (m.get("architecture") or {}).get("input_modalities") or []
            if "image" in modalities:
                vision.append(mid)
        # Vision-capable models first even for text — they handle both.
        free.sort(key=lambda mid: mid not in vision)
        self._discovered = (time.time(), free, vision)
        print(f"[LLM] free-model pool refreshed: {len(free)} models ({len(vision)} with vision)")
        return free, vision

    # Errors worth retrying on the next model in the chain.
    _RETRYABLE = (402, 404, 408, 429, 500, 502, 503, 529)

    def chat(self, system: str, history: list) -> str:
        messages = [{"role": "system", "content": system}]
        for turn in history:
            messages.append({"role": turn["role"], "content": self._convert(turn["content"])})

        has_images = any(
            part["type"] == "image_jpeg_b64" for turn in history for part in turn["content"]
        )
        all_free, vision_free = self._discover_free_models()
        pool = vision_free if has_images else all_free

        seen, models = set(), []
        for mid in [settings.llm_model, *settings.llm_fallback_models, *pool]:
            if mid and mid not in seen:
                seen.add(mid)
                models.append(mid)
        models = models[:12]  # enough depth to survive congestion, bounded latency

        last_error = None
        for i, model in enumerate(models):
            is_last = i == len(models) - 1
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    max_tokens=settings.max_tokens,
                    messages=messages,
                )
            except self._openai.APIStatusError as exc:
                detail = getattr(exc, "message", str(exc))
                if exc.status_code in self._RETRYABLE and not is_last:
                    last_error = f"{model}: {exc.status_code}"
                    continue  # try the next model in the chain
                hint = "if 404/400, the model id may be wrong or no longer free; pick another"
                if exc.status_code == 401:
                    hint = f"auth problem — {_key_diagnostic()}"
                elif exc.status_code == 429:
                    hint = (
                        "every model in the chain is rate-limited right now "
                        f"(tried: {', '.join(models)}) — wait a minute, or run OmniRoute / "
                        "add more ids to JARVIS_LLM_FALLBACK_MODELS"
                    )
                raise LLMError(
                    f"LLM gateway error {exc.status_code}: {detail} "
                    f"(model={model!r}, base_url={settings.llm_base_url!r} — {hint})."
                ) from exc
            except self._openai.APIConnectionError as exc:
                raise LLMError(
                    f"Cannot reach LLM gateway at {settings.llm_base_url!r}. "
                    "Is OmniRoute running / is your network up?"
                ) from exc

            choice = response.choices[0] if response.choices else None
            text = (choice.message.content or "") if choice else ""
            if text.strip():
                self.last_model = model
                if model != settings.llm_model:
                    print(f"[LLM] primary busy — answered by fallback: {model}")
                return text.strip()
            last_error = f"{model}: empty response"
            if not is_last:
                continue

        raise LLMError(f"All models in the chain failed (last: {last_error}).")

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


def _key_diagnostic() -> str:
    key = settings.llm_api_key
    if not key:
        return "NO API key was loaded; put OPENROUTER_API_KEY=sk-or-... in jarvis_hud/.env and restart"
    return (
        f"a key WAS loaded (starts {key[:9]!r}, {len(key)} chars) but the gateway rejected it — "
        "check it has no quotes/spaces, is not the sk-or-... placeholder, and is still valid on openrouter.ai/keys"
    )


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
