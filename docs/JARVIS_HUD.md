# JARVIS HUD — Personal Vision + Voice Assistant

A self-contained Python module (`jarvis_hud/`) that turns this repo into a
personal, Iron-Man-style assistant:

- **Camera in**: your Iriun Webcam (or any OS camera device)
- **Hand tracking**: MediaPipe Hands — per-hand finger count + gesture (based on the owner's original `hand_tracking.py`)
- **Face tracking**: MediaPipe Face Mesh — presence, rough head yaw/pitch, mouth-open
- **Objects in hand** (optional): YOLOv8-nano via `ultralytics`
- **Brain**: Claude **Fable 5** (`claude-fable-5`) through the official Anthropic SDK, with automatic server-side fallback to `claude-opus-4-8` on safety declines
- **HUD**: browser page styled as glowing blue arc-reactor rings on dark navy, camera feed in the core, telemetry left, console right
- **Voice**: mic input via the browser (Chrome/Edge Web Speech API); voice output via ElevenLabs (optional) with browser speech-synthesis fallback

This module is intentionally independent of the TypeScript "control layer"
app in `src/` — the two can coexist and neither breaks the other.

## What you need to run it (personal use)

| Requirement | Notes |
|---|---|
| Python 3.10 – 3.12 | MediaPipe does **not** support 3.13 yet ✅ |
| An Anthropic API key | https://platform.claude.com → `ANTHROPIC_API_KEY`. Fable 5 requires an org with ≥30-day data retention (default). |
| Iriun Webcam | Phone app + desktop client installed; it appears as a normal OS webcam |
| Chrome or Edge | Only these ship the Web Speech API for mic input; the rest of the HUD works in any browser |
| ElevenLabs account (optional) | `ELEVENLABS_API_KEY` + a `ELEVENLABS_VOICE_ID` you have rights to use |

## Setup

```bash
cd jarvis
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r jarvis_hud/requirements.txt

cp jarvis_hud/.env.example jarvis_hud/.env
# edit jarvis_hud/.env — at minimum set ANTHROPIC_API_KEY

python -m jarvis_hud
# open http://127.0.0.1:8765
```

### Iriun camera not found?

Iriun is often **not** device 0. Set `JARVIS_CAMERA_INDEX=1` (or 2) in
`jarvis_hud/.env` and restart. On Windows, make sure the Iriun desktop
client is running and the phone is connected before starting JARVIS.

### Optional: object detection

```bash
pip install ultralytics       # pulls in torch — big download
# then in .env:
JARVIS_ENABLE_OBJECTS=1
```

Detections overlapping a tracked hand are flagged as **held** and shown in
the OBJECTS row of the HUD.

## Using it

- The center core shows the live camera with hand skeleton + face mesh drawn on.
- Type in the console or press the mic button and speak.
- Every message automatically carries the current tracking telemetry, so you can ask *"how many fingers am I holding up?"* without sending an image.
- Tick **attach frame** to send the actual camera frame to Claude for questions like *"what am I holding?"* or *"how do I look?"*.
- Tick **voice** to have replies spoken (ElevenLabs if configured, otherwise the browser's built-in voice).
- `POST /api/reset` (or restart) clears conversation memory.

## Security / control model

- Server binds to `127.0.0.1` only — nothing is exposed to your network.
- The brain has **no tools wired in**: it can see telemetry/frames you send and answer, but it cannot open, delete, or send anything. Its system prompt forbids claiming otherwise.
- Real-world capabilities (files, apps, email, MCP connectors) should be added later as explicit, approval-gated tools — that matches the approval-first philosophy of the main JARVIS control-layer app in this repo.
- Your camera frames go to Anthropic's API **only** when "attach frame" is ticked; telemetry JSON goes with each chat message.

## Configuration reference

All via environment or `jarvis_hud/.env` — see `.env.example`. Highlights:

| Variable | Default | Meaning |
|---|---|---|
| `JARVIS_BOT_NAME` | `JARVIS` | The bot's name (HUD title + persona) |
| `JARVIS_CAMERA_INDEX` | `0` | OS camera device index |
| `JARVIS_MODEL` | `claude-fable-5` | Brain model |
| `JARVIS_FALLBACK_MODEL` | `claude-opus-4-8` | Server-side refusal fallback |
| `JARVIS_ENABLE_FACE` | `1` | Face mesh tracking |
| `JARVIS_ENABLE_OBJECTS` | `0` | YOLO object detection |
| `JARVIS_STREAM_FPS` | `15` | HUD frame rate |
| `JARVIS_PORT` | `8765` | HTTP port |

## About the reference repos (handholding / holdhand2)

Those are forks of **ARCTIC** (bimanual hand-object dataset) and **HOLD**
(CVPR'24 hand+object 3D reconstruction). They are research training
pipelines — GPU-heavy, dataset-registration-gated, not real-time. Useful to
*study* hand-object interaction; not components of this assistant. The
real-time path here (MediaPipe + optional YOLO) is the practical one.
