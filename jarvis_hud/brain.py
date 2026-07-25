"""JARVIS brain — provider-agnostic (Anthropic Claude, or any
OpenAI-compatible gateway such as OpenRouter / a local OmniRoute).

- The system prompt is static; live camera telemetry is injected into the
  user turn.
- No autonomous tools are wired in: JARVIS answers, reports, and asks.
  Anything that acts on the owner's machine/accounts must go through
  explicitly approved integrations, by design.
- scan() is a one-shot vision call that returns labeled callout annotations
  for whatever product/object is shown to the camera.
"""

import json
import re

from .config import settings
from .llm import LLMError, build_provider
from .memory import Memory

SYSTEM_PROMPT_TEMPLATE = """\
You are {bot_name}, a personal AI assistant inspired by Iron Man's JARVIS, \
serving one owner: {owner_name}. You run locally on the owner's machine with \
a live camera feed (hand tracking, face tracking, optional object detection) \
whose telemetry is provided to you in each message.

Personality: composed, precise, dryly witty, loyal. Address the owner \
directly. Keep spoken-style responses short (1-4 sentences) unless asked for \
detail — your replies may be read aloud by a voice engine.

Hard rules:
- You may inform, analyze, and advise. You must NOT claim to have taken \
real-world actions (opening apps, deleting files, sending messages) — you \
have no such tools here. If asked, say what you would need and ask for \
approval.
- Never invent camera observations. Only describe what the telemetry or an \
attached frame actually shows. If the camera is off or telemetry is empty, \
say so.
- If you don't know something, say so plainly.

Memory: when the owner tells you a durable personal fact, preference, or \
standing instruction (name, projects, likes, schedule, "always do X"), append \
<remember>that fact, third person, one line</remember> at the very end of \
your reply. Only genuinely durable facts — never trivia, never things already \
in your long-term memory list.
"""

SCAN_PROMPT = """\
Analyze this camera frame like an Iron-Man HUD. Identify the main product / \
object being shown (prefer whatever is held in a hand or centered) and its \
visible components or notable features.{hint}

Reply with ONLY a JSON array, no prose, 3 to 7 items:
[{{"label": "short name", "detail": "one-line description", "x": 0.42, "y": 0.31}}]

x and y are normalized 0..1 coordinates of the point on the image the label \
refers to (0,0 = top-left). The first item must be the overall product with \
its most specific name.\
"""


class JarvisBrain:
    def __init__(self):
        self._provider = None
        self._base_system = SYSTEM_PROMPT_TEMPLATE.format(
            bot_name=settings.bot_name, owner_name=settings.owner_name
        )
        self.memory = Memory()
        self._history = self.memory.load_history()  # survives restarts

    @property
    def _system(self) -> str:
        return self._base_system + self.memory.facts_block()

    def _get_provider(self):
        if self._provider is None:
            self._provider = build_provider()
        return self._provider

    def reset(self):
        self._history = []
        self.memory.clear_history()

    @property
    def provider_name(self) -> str:
        try:
            return self._get_provider().name
        except LLMError as exc:
            return f"unconfigured ({exc})"

    def chat(self, message: str, tracking: dict | None = None, frame_jpeg_b64: str | None = None):
        """One conversational turn. Returns the assistant's reply text."""
        content = []
        if frame_jpeg_b64:
            content.append({"type": "image_jpeg_b64", "data": frame_jpeg_b64})
        text = message
        if tracking is not None:
            text += "\n\n<camera_telemetry>\n" + json.dumps(tracking) + "\n</camera_telemetry>"
        content.append({"type": "text", "text": text})

        self._history.append({"role": "user", "content": content})
        try:
            reply = self._get_provider().chat(self._system, self._history)
        except LLMError:
            self._history.pop()
            raise
        if not reply:
            reply = "(no response)"

        # Harvest facts the model chose to remember, then hide the tags.
        for fact in re.findall(r"<remember>(.*?)</remember>", reply, re.DOTALL):
            self.memory.add_fact(fact)
        reply = re.sub(r"\s*<remember>.*?</remember>\s*", " ", reply, flags=re.DOTALL).strip()

        self._history.append({"role": "assistant", "content": [{"type": "text", "text": reply}]})
        self.memory.save_history(self._history)
        return reply

    def research(self, page_markdown: str, url: str, question: str = "") -> str:
        """One-shot analysis of crawled page content (does not touch history)."""
        ask = question or "Summarize the key points of this page for me, briefly."
        turn = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"I crawled this page: {url}\n\n"
                            f"<page_content>\n{page_markdown}\n</page_content>\n\n{ask}"
                        ),
                    }
                ],
            }
        ]
        return self._get_provider().chat(self._system, turn)

    def look_at_image(self, jpeg_b64: str, question: str) -> str:
        """One-shot vision question about an arbitrary image (e.g. a screen
        capture). Does not touch chat history."""
        turn = [
            {
                "role": "user",
                "content": [
                    {"type": "image_jpeg_b64", "data": jpeg_b64},
                    {"type": "text", "text": question},
                ],
            }
        ]
        return self._get_provider().chat(self._system, turn)

    def scan(self, frame_jpeg_b64: str, hint: str = ""):
        """One-shot HUD scan: returns a list of {label, detail, x, y}."""
        hint_text = f" The owner adds: {hint!r}." if hint else ""
        turn = [
            {
                "role": "user",
                "content": [
                    {"type": "image_jpeg_b64", "data": frame_jpeg_b64},
                    {"type": "text", "text": SCAN_PROMPT.format(hint=hint_text)},
                ],
            }
        ]
        raw = self._get_provider().chat(
            "You are a precise visual analysis engine. Output only valid JSON.", turn
        )
        return _parse_annotations(raw)


def _parse_annotations(raw: str):
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        raise LLMError(f"Scan model did not return JSON. Raw output: {raw[:300]}")
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMError(f"Scan model returned invalid JSON: {exc}") from exc

    annotations = []
    for item in items:
        if not isinstance(item, dict) or "label" not in item:
            continue
        try:
            x = min(1.0, max(0.0, float(item.get("x", 0.5))))
            y = min(1.0, max(0.0, float(item.get("y", 0.5))))
        except (TypeError, ValueError):
            x, y = 0.5, 0.5
        annotations.append(
            {
                "label": str(item["label"])[:60],
                "detail": str(item.get("detail", ""))[:200],
                "x": x,
                "y": y,
            }
        )
    if not annotations:
        raise LLMError("Scan model returned an empty result.")
    return annotations
