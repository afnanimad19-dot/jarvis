"""FastAPI server: serves the HUD page, streams camera frames + tracking
over a WebSocket, and exposes chat (LLM), scan (vision labeling), gesture
mouse control, and TTS (ElevenLabs) endpoints.

Binds to 127.0.0.1 by default — this is a personal, local assistant.
"""

import asyncio
import base64
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import voice
from .brain import JarvisBrain
from .config import settings
from .gesture import GestureMouse
from .llm import LLMError
from .vision.camera import VisionEngine

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="JARVIS HUD", version="0.2.0")
engine = VisionEngine()
brain = JarvisBrain()
gesture = GestureMouse(engine)


@app.on_event("startup")
def _startup():
    engine.start()


@app.on_event("shutdown")
def _shutdown():
    gesture.set_enabled(False)
    engine.stop()


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/config")
def get_config():
    return {
        "bot_name": settings.bot_name,
        "provider": brain.provider_name,
        "tts_available": voice.is_configured(),
        "gesture_enabled": gesture.enabled,
    }


class ChatRequest(BaseModel):
    message: str
    attach_frame: bool = False


@app.post("/api/chat")
def chat(req: ChatRequest):
    jpeg, tracking = engine.snapshot()
    frame_b64 = None
    if req.attach_frame and jpeg:
        frame_b64 = base64.standard_b64encode(jpeg).decode("ascii")
    try:
        reply = brain.chat(req.message, tracking=tracking, frame_jpeg_b64=frame_b64)
    except LLMError as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})
    return {"reply": reply}


class ScanRequest(BaseModel):
    hint: str = ""


@app.post("/api/scan")
def scan(req: ScanRequest):
    jpeg, _tracking = engine.snapshot()
    if not jpeg:
        return JSONResponse(status_code=409, content={"error": "No camera frame available."})
    frame_b64 = base64.standard_b64encode(jpeg).decode("ascii")
    try:
        annotations = brain.scan(frame_b64, hint=req.hint)
    except LLMError as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})
    # Return the exact frame that was analyzed so overlay lines line up.
    return {"annotations": annotations, "frame": frame_b64}


class GestureRequest(BaseModel):
    enabled: bool


@app.post("/api/gesture")
def set_gesture(req: GestureRequest):
    ok = gesture.set_enabled(req.enabled)
    if not ok:
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Gesture control unavailable: {gesture.error} "
                "(pip install pynput screeninfo, and run on a machine with a display)."
            },
        )
    return {"enabled": gesture.enabled}


@app.post("/api/reset")
def reset():
    brain.reset()
    return {"ok": True}


class TTSRequest(BaseModel):
    text: str


@app.post("/api/tts")
async def tts(req: TTSRequest):
    if not voice.is_configured():
        return JSONResponse(
            status_code=404,
            content={"error": "TTS not configured (set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID)."},
        )
    audio = await voice.synthesize(req.text)
    return Response(content=audio, media_type="audio/mpeg")


@app.websocket("/ws/vision")
async def ws_vision(ws: WebSocket):
    await ws.accept()
    interval = 1.0 / max(1, settings.stream_fps)
    try:
        while True:
            jpeg, tracking = engine.snapshot()
            payload = {"type": "vision", "tracking": tracking, "gesture": gesture.enabled}
            if jpeg:
                payload["frame"] = base64.standard_b64encode(jpeg).decode("ascii")
            await ws.send_json(payload)
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        pass


def main():
    import uvicorn

    print(f"[{settings.bot_name}] HUD online -> http://{settings.host}:{settings.port}")
    print(f"[{settings.bot_name}] brain provider: {brain.provider_name}")
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")


if __name__ == "__main__":
    main()
