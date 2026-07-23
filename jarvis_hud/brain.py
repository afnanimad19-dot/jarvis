"""JARVIS brain — Claude Fable 5 via the official Anthropic SDK.

Design decisions:
- Model is claude-fable-5 (per owner's choice), with the server-side refusal
  fallback to claude-opus-4-8 enabled by default so a safety-classifier
  decline degrades gracefully instead of failing.
- Fable 5's thinking is always on; we do NOT send a `thinking` parameter.
- The system prompt is static (prompt-caching friendly); live camera
  telemetry is injected into the user turn, not the system prompt.
- No autonomous tools are wired in: JARVIS answers, reports, and asks.
  Anything that acts on the owner's machine/accounts must go through
  explicitly approved integrations (MCP), by design.
"""

import json

import anthropic

from .config import settings

FALLBACK_BETA = "server-side-fallback-2026-06-01"

SYSTEM_PROMPT_TEMPLATE = """\
You are {bot_name}, a personal AI assistant inspired by Iron Man's JARVIS, \
serving one owner: {owner_name}. You run locally on the owner's machine with \
a live camera feed (hand tracking, face tracking, optional object detection) \
whose telemetry is provided to you in each message.

Personality: composed, precise, dryly witty, loyal. Address the owner \
directly. Keep spoken-style responses short (1-4 sentences) unless asked for \
detail — your replies may be read aloud by a voice engine.

Hard rules:
- You may inform, analyze, fetch, and advise. You must NOT claim to have \
taken real-world actions (opening apps, deleting files, sending messages) — \
you have no such tools here. If asked, say what you would need and ask for \
approval.
- Never invent camera observations. Only describe what the telemetry or an \
attached frame actually shows. If the camera is off or telemetry is empty, \
say so.
- If you don't know something, say so plainly.
"""


class JarvisBrain:
    def __init__(self):
        self._client = anthropic.Anthropic()
        self._system = SYSTEM_PROMPT_TEMPLATE.format(
            bot_name=settings.bot_name, owner_name=settings.owner_name
        )
        self._history = []  # alternating user/assistant turns

    def reset(self):
        self._history = []

    def chat(self, message: str, tracking: dict | None = None, frame_jpeg_b64: str | None = None):
        """One conversational turn. Returns the assistant's reply text."""
        content = []
        if frame_jpeg_b64:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": frame_jpeg_b64,
                    },
                }
            )
        text = message
        if tracking is not None:
            text += "\n\n<camera_telemetry>\n" + json.dumps(tracking) + "\n</camera_telemetry>"
        content.append({"type": "text", "text": text})

        self._history.append({"role": "user", "content": content})

        try:
            response = self._client.beta.messages.create(
                model=settings.model,
                max_tokens=settings.max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": self._system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                betas=[FALLBACK_BETA],
                fallbacks=[{"model": settings.fallback_model}],
                messages=self._history,
            )
        except anthropic.APIStatusError as exc:
            # Roll back the failed turn so history stays consistent.
            self._history.pop()
            raise RuntimeError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            self._history.pop()
            raise RuntimeError("Cannot reach the Anthropic API (network error).") from exc

        if response.stop_reason == "refusal":
            self._history.pop()
            return "I must decline that request."

        # Preserve full content (incl. thinking blocks) for correct replay.
        self._history.append({"role": "assistant", "content": response.content})
        reply = "".join(block.text for block in response.content if block.type == "text")
        return reply.strip() or "(no response)"
