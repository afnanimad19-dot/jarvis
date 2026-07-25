"""FastAPI server: serves the HUD page, streams camera frames + tracking
over a WebSocket, and exposes chat (LLM), scan (vision labeling), gesture
mouse control, and TTS (ElevenLabs) endpoints.

Binds to 127.0.0.1 by default — this is a personal, local assistant.
"""

import asyncio
import base64
import os
import webbrowser

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import datetime

from . import control, screen, voice
from .brain import JarvisBrain
from .config import settings
from .gesture import GestureMouse
from .integrations import crawler, postiz, telegram, weather, whatsapp
from .llm import LLMError
from .reminders import ReminderError, Reminders
from .vision.camera import VisionEngine

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="JARVIS HUD", version="0.2.0")
engine = VisionEngine()
brain = JarvisBrain()
gesture = GestureMouse(engine)
reminders = Reminders()


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
        "crawl_available": crawler.is_enabled(),
        "postiz_available": postiz.is_configured(),
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
    return {"reply": reply, "model": brain.last_model}


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


class CrawlRequest(BaseModel):
    url: str
    question: str = ""


@app.post("/api/crawl")
async def crawl_url(req: CrawlRequest):
    try:
        markdown = await crawler.crawl(req.url)
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})
    try:
        answer = brain.research(markdown, req.url, req.question)
    except LLMError as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})
    return {"answer": answer, "chars_crawled": len(markdown)}


@app.get("/api/social/channels")
def social_channels():
    if not postiz.is_configured():
        return JSONResponse(
            status_code=404,
            content={"error": "Postiz not configured (set POSTIZ_URL and POSTIZ_API_KEY)."},
        )
    try:
        return {"channels": postiz.list_channels()}
    except Exception as exc:
        return JSONResponse(status_code=502, content={"error": f"Postiz error: {exc}"})


class DraftRequest(BaseModel):
    text: str
    channel_ids: list[str] = []


@app.post("/api/social/draft")
def social_draft(req: DraftRequest):
    """Creates a DRAFT in Postiz — publishing stays a manual step in its UI."""
    if not postiz.is_configured():
        return JSONResponse(
            status_code=404,
            content={"error": "Postiz not configured (set POSTIZ_URL and POSTIZ_API_KEY)."},
        )
    try:
        channel_ids = req.channel_ids
        if not channel_ids:
            channels = postiz.list_channels()
            channel_ids = [c["id"] for c in channels if isinstance(c, dict) and "id" in c]
        result = postiz.create_draft(req.text, channel_ids)
    except Exception as exc:
        return JSONResponse(status_code=502, content={"error": f"Postiz error: {exc}"})
    return {"ok": True, "draft": result, "channels": channel_ids}


class ScreenRequest(BaseModel):
    question: str = ""
    monitor: int = 0  # 0 = all monitors combined, 1..n = a single display


@app.post("/api/screen")
def look_at_screen(req: ScreenRequest):
    """Capture the monitor(s) and answer a question about what's visible."""
    try:
        jpeg = screen.capture_jpeg(monitor=req.monitor)
    except RuntimeError as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
    question = req.question or "Describe what is on my screen right now, briefly."
    try:
        answer = brain.look_at_image(base64.standard_b64encode(jpeg).decode("ascii"), question)
    except LLMError as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})
    return {"answer": answer, "monitors": screen.monitor_count()}


class SearchRequest(BaseModel):
    query: str


@app.post("/api/search")
def web_search(req: SearchRequest):
    """Open a Google search in the default browser (Opera if that's yours)."""
    q = req.query.strip()
    if not q:
        return JSONResponse(status_code=400, content={"error": "Empty query."})
    webbrowser.open("https://www.google.com/search?q=" + q.replace(" ", "+"))
    return {"ok": True, "query": q}


class WindowRequest(BaseModel):
    action: str  # maximize | minimize | restore


@app.post("/api/window")
def window(req: WindowRequest):
    try:
        title = control.window_action(req.action)
    except RuntimeError as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return {"ok": True, "title": title}


@app.get("/api/system")
def system():
    try:
        return control.system_status()
    except RuntimeError as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


class AppRequest(BaseModel):
    name: str


@app.post("/api/app")
def open_app(req: AppRequest):
    try:
        opened = control.open_app(req.name)
    except RuntimeError as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return {"ok": True, "app": opened}


class MediaRequest(BaseModel):
    action: str  # volume_up | volume_down | mute | play_pause | next | previous
    times: int = 1


@app.post("/api/media")
def media(req: MediaRequest):
    try:
        control.media_action(req.action, req.times)
    except RuntimeError as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return {"ok": True, "action": req.action}


@app.get("/api/weather")
async def get_weather(city: str = ""):
    try:
        w = await weather.get_weather(city)
    except Exception as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})
    return {"weather": w, "spoken": weather.spoken(w)}


@app.post("/api/brief")
async def daily_brief():
    data = {"now": datetime.datetime.now().strftime("%A, %B %d, %Y — %H:%M")}
    try:
        data["weather"] = await weather.get_weather("")
    except Exception as exc:
        data["weather"] = f"unavailable ({exc})"
    data["reminders_today"] = [
        {"text": r["text"], "at": datetime.datetime.fromtimestamp(r["due"]).strftime("%H:%M")}
        for r in reminders.pending()
        if datetime.datetime.fromtimestamp(r["due"]).date() == datetime.date.today()
    ]
    try:
        data["system"] = control.system_status()
    except RuntimeError:
        pass
    try:
        brief = brain.compose_brief(data)
    except LLMError as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})
    return {"brief": brief}


class ReminderRequest(BaseModel):
    action: str  # add | cancel | clear
    text: str = ""


@app.get("/api/reminders")
def reminders_list():
    return {
        "reminders": [
            {"text": r["text"],
             "at": datetime.datetime.fromtimestamp(r["due"]).strftime("%a %H:%M")}
            for r in reminders.pending()
        ]
    }


@app.post("/api/reminders")
def reminders_edit(req: ReminderRequest):
    if req.action == "add":
        try:
            item = reminders.add(req.text)
        except ReminderError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})
        return {
            "ok": True,
            "text": item["text"],
            "at": datetime.datetime.fromtimestamp(item["due"]).strftime("%H:%M"),
        }
    if req.action == "cancel":
        return {"ok": True, "removed": reminders.cancel(req.text)}
    if req.action == "clear":
        return {"ok": True, "cleared": reminders.clear()}
    return JSONResponse(status_code=400, content={"error": f"Unknown action {req.action!r}"})


class MessageRequest(BaseModel):
    channel: str  # telegram | whatsapp
    to: str = ""
    text: str


@app.post("/api/message")
async def send_message(req: MessageRequest):
    """Owner-confirmed outbound message. The HUD asks for confirmation
    BEFORE calling this endpoint — nothing is sent un-confirmed."""
    try:
        if req.channel == "telegram":
            await telegram.send(req.text, chat_id=req.to)
            return {"ok": True, "channel": "telegram"}
        if req.channel == "whatsapp":
            number = await asyncio.to_thread(whatsapp.send, req.to, req.text)
            return {"ok": True, "channel": "whatsapp", "to": number}
    except Exception as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})
    return JSONResponse(status_code=400, content={"error": f"Unknown channel {req.channel!r}"})


class MemoryRequest(BaseModel):
    action: str  # add | remove | clear
    text: str = ""


@app.get("/api/memory")
def memory_list():
    return {"facts": brain.memory.facts()}


@app.post("/api/memory")
def memory_edit(req: MemoryRequest):
    if req.action == "add":
        added = brain.memory.add_fact(req.text)
        return {"ok": True, "added": added}
    if req.action == "remove":
        return {"ok": True, "removed": brain.memory.remove_facts(req.text)}
    if req.action == "clear":
        return {"ok": True, "cleared": brain.memory.clear_facts()}
    return JSONResponse(status_code=400, content={"error": f"Unknown action {req.action!r}"})


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
    try:
        audio, mime = await voice.synthesize(req.text)
    except Exception as exc:  # VoxCPM load errors, ElevenLabs network errors, etc.
        return JSONResponse(status_code=502, content={"error": str(exc)})
    if not audio:
        return JSONResponse(status_code=404, content={"error": "TTS produced no audio."})
    return Response(content=audio, media_type=mime)


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
            due = reminders.pop_due()
            if due:
                payload["reminders_due"] = [r["text"] for r in due]
            await ws.send_json(payload)
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        pass


def _mask(secret: str) -> str:
    return f"loaded ({secret[:9]}… {len(secret)} chars)" if secret else "NOT FOUND"


def main():
    import uvicorn

    name = settings.bot_name
    print(f"[{name}] HUD online -> http://{settings.host}:{settings.port}")
    print(f"[{name}] brain provider: {brain.provider_name}")
    if brain.provider_name == "openai_compatible":
        print(f"[{name}] LLM gateway:  {settings.llm_base_url}  model: {settings.llm_model}")
        print(f"[{name}] LLM api key:  {_mask(settings.llm_api_key)}")
    print(f"[{name}] voice engine: {voice.provider_name()}")
    if settings.elevenlabs_api_key or settings.elevenlabs_voice_id:
        print(f"[{name}] elevenlabs key: {_mask(settings.elevenlabs_api_key)}  "
              f"voice id: {settings.elevenlabs_voice_id or 'NOT SET'}")
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")


if __name__ == "__main__":
    main()
