# JARVIS HUD — Personal Vision + Voice Assistant

A self-contained Python module (`jarvis_hud/`) that turns this repo into a
personal, Iron-Man-style assistant:

- **Camera in**: your Iriun Webcam (or any OS camera device)
- **Hand tracking**: MediaPipe Hands — per-hand finger count, gestures, pinch detection (based on the owner's original `hand_tracking.py`)
- **Face tracking**: MediaPipe Face Mesh — presence, rough head yaw/pitch, mouth-open
- **SCAN mode**: show a product to the camera, press **◈ SCAN** — a vision model identifies it and its components, and the HUD draws callout lines + labels over the frozen frame
- **Gesture mouse control**: pinch-and-drag windows/widgets with your hand, across the full multi-monitor desktop
- **Brain**: pluggable — Anthropic Claude, **OpenRouter** (free-tier models), or a local **OmniRoute** gateway (one OpenAI-compatible endpoint over 90+ free provider tiers)
- **HUD**: browser page styled as glowing blue arc-reactor rings on dark navy, camera feed in the core, telemetry left, console right
- **Voice**: mic input via the browser (Chrome/Edge Web Speech API); voice output via ElevenLabs (optional) with browser speech-synthesis fallback
- **Objects in hand** (optional): YOLOv8-nano via `ultralytics`
- **Optional integrations**: browser-use (web tasks), listmonk (email)

This module is independent of the TypeScript "control layer" app in `src/` —
the two coexist; neither breaks the other.

## Step-by-step setup (Windows, Python 3.11)

**1. Get the code** — any folder on any drive works. Example for the **F: drive**:

```bat
F:
mkdir F:\Jarvis
cd F:\Jarvis
git clone -b claude/jarvis-ai-bot-tracking-rglwl7 https://github.com/afnanimad19-dot/jarvis.git
cd jarvis
```

Everything (code, virtual env, downloaded models) then lives under
`F:\Jarvis` — nothing project-related is written to C:. (Python itself and
pip's package cache stay wherever Python is installed; that's normal.)

**2. Create a virtual env + install:**

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r jarvis_hud\requirements.txt
```

**3. Configure keys:**

```bat
copy jarvis_hud\.env.example jarvis_hud\.env
notepad jarvis_hud\.env
```

- **OpenRouter**: set `OPENROUTER_API_KEY` and a *vision-capable* `JARVIS_LLM_MODEL` (free ids change — check https://openrouter.ai/models, filter "free", pick one that lists image input).
- **OmniRoute** (your fork — a local gateway aggregating free providers): run it (`npx omniroute` or Docker per its README), then set `JARVIS_LLM_BASE_URL=http://localhost:20128/v1` and the model/key it gives you.
- **ElevenLabs**: paste `ELEVENLABS_API_KEY` and an `ELEVENLABS_VOICE_ID` (from https://elevenlabs.io → Voices → copy voice ID).

**4. Start Iriun** (phone app + Windows client, same network), then:

```bat
python -m jarvis_hud
```

**5. Open http://127.0.0.1:8765 in Chrome or Edge.**

Camera black / "cannot open"? Iriun is usually **not** device 0 — set
`JARVIS_CAMERA_INDEX=1` (or 2) in `.env` and restart.

## Features and how to use them

### Chat / voice
Type in the console or press the mic button. Every message carries live
tracking telemetry ("how many fingers am I holding up?" works without an
image). Tick **attach frame** to send the actual camera frame ("what am I
holding?"). Tick **voice** for spoken replies (ElevenLabs if configured,
otherwise the browser voice).

### SCAN mode (product labeling)
Hold a product up to the camera and press **◈ SCAN** under the reactor core.
The current frame is frozen and sent to your vision model, which returns the
product name + component labels; the HUD renders them as glowing callout
lines. Requires a vision-capable model (`JARVIS_LLM_MODEL`). Accuracy of the
pointer positions depends on the model — big models point well, small free
ones are approximate.

### Gesture mouse control (3 monitors)
Toggle **GESTURE CTRL** in the sensors panel. Your index fingertip becomes
the mouse pointer, mapped across the *entire* virtual desktop (all monitors,
via `screeninfo`). **Pinch** (thumb+index together) = press and hold left
mouse button — pinch a window's title bar, move your hand, release to drop
it on another monitor. `JARVIS_GESTURE_HAND` picks the controlling hand,
`JARVIS_GESTURE_SMOOTHING` trades responsiveness vs. jitter.
JARVIS keeps running in the background the whole time.

### Optional: object detection
`pip install ultralytics` then `JARVIS_ENABLE_OBJECTS=1`. Detections
overlapping a tracked hand are flagged **held** in the OBJECTS row.

### Optional: web tasks (browser-use)
`pip install browser-use`, `playwright install chromium`, set
`JARVIS_ENABLE_WEBTASK=1`. `jarvis_hud/integrations/web_task.py` runs a
browser agent with the same LLM gateway. Honest caveat: multi-step browsing
needs a capable model; small free-tier models are unreliable at it.

### Crawl & research (crawl4ai)
`pip install crawl4ai` then `crawl4ai-setup`, and set `JARVIS_ENABLE_CRAWL=1`.
In the console type:

```
/crawl https://example.com/page  what are the main features of this product?
```

JARVIS fetches the page as clean markdown and answers your question about it
(or summarizes if you ask nothing). Reality check: Instagram/VSCO/TikTok/X
aggressively block crawlers and hide content behind login — public pages,
blogs, docs and product pages work far better.

### Social media drafts (Postiz)
Postiz is a separate self-hosted scheduler (Docker). Run it, connect your
social channels in its UI, create an API key (Settings → Public API), then:

```
POSTIZ_URL=http://localhost:5000
POSTIZ_API_KEY=...
```

In the console: `/post your post text here` → JARVIS creates a **draft** on
your connected channels. You review and publish inside Postiz — JARVIS never
auto-publishes, by design. Typical flow: `/crawl` a topic → ask JARVIS to
write the post → `/post` the text.

### Local voice / voice cloning (VoxCPM)
No ElevenLabs credits? `pip install voxcpm` and set
`JARVIS_TTS_PROVIDER=voxcpm` (or leave `auto` — it's the fallback when
ElevenLabs keys are absent). First run downloads the OpenBMB VoxCPM-0.5B
model. To clone a voice: record a short clean WAV, set
`JARVIS_VOXCPM_PROMPT_WAV` + `JARVIS_VOXCPM_PROMPT_TEXT` (its transcript).
Runs on CPU but a GPU makes it much faster. Use voices you have rights to.

### Optional: email (listmonk)
listmonk is a separate self-hosted mail server (Docker). Once yours runs,
set `LISTMONK_URL` / `LISTMONK_USER` / `LISTMONK_TOKEN` and use
`jarvis_hud/integrations/listmonk.py` (add subscriber, send transactional
email). Deliberately **not** wired as an autonomous chat tool — sending
email stays an owner-approved action.

## Security / control model

- Server binds to `127.0.0.1` only.
- The chat brain has **no autonomous action tools**; its prompt forbids claiming otherwise. Gesture control and any future tools are explicit toggles you flip.
- Camera frames leave your machine **only** on "attach frame" or SCAN, going to whichever LLM gateway you configured. With a local OmniRoute + local models, nothing needs to leave at all.

## Configuration reference

All via environment or `jarvis_hud/.env` — see `.env.example`. Highlights:

| Variable | Default | Meaning |
|---|---|---|
| `JARVIS_LLM_PROVIDER` | `auto` | `anthropic` \| `openai_compatible` (auto-detects by keys) |
| `JARVIS_LLM_BASE_URL` | OpenRouter | Or `http://localhost:20128/v1` for OmniRoute |
| `JARVIS_LLM_MODEL` | a free Qwen VL id | Must support images for SCAN/attach-frame |
| `JARVIS_BOT_NAME` | `JARVIS` | Bot name (HUD title + persona) |
| `JARVIS_CAMERA_INDEX` | `0` | OS camera device index |
| `JARVIS_GESTURE_HAND` | `Right` | Hand that drives the pointer |
| `JARVIS_STREAM_FPS` | `15` | HUD frame rate |
| `JARVIS_PORT` | `8765` | HTTP port |

## About the reference repos

- **handholding / holdhand2** — forks of ARCTIC and HOLD: research training
  pipelines (GPU, dataset registration), not real-time components. Study
  material only; MediaPipe + a hosted VLM is the practical path used here.
- **OmniRoute** — local AI gateway exposing ~290 providers / 90+ free tiers
  through one OpenAI-compatible endpoint (`http://localhost:20128/v1`).
  Supported directly via the `openai_compatible` provider.
- **browser-use** — AI browser automation; integrated as an optional module.
- **listmonk** — self-hosted newsletter/mail server; thin client included.
- **NVIDIA Eagle (Embodied)** — research vision-language models for robots.
  Running them locally needs serious GPU hardware; the SCAN feature achieves
  the "label what I'm holding" effect with hosted VLMs instead.
- **VoxCPM** — OpenBMB's local TTS with voice cloning; integrated as a TTS
  provider (`JARVIS_TTS_PROVIDER=voxcpm`).
- **crawl4ai** — LLM-friendly crawler; integrated as the `/crawl` command.
- **postiz-app** — self-hosted social scheduler; integrated as the `/post`
  command (drafts only — publishing stays manual in Postiz).
- **claude-seo** — a Claude Code *plugin* (`/seo audit <url>`, 25 sub-skills).
  It runs inside Claude Code, not inside JARVIS — install it there per its
  README and use it alongside JARVIS.
- **floci** — a local AWS emulator (LocalStack replacement) for developing
  and testing cloud software. Unrelated to a personal assistant; deliberately
  not integrated. Use it when you build AWS-backed apps.
