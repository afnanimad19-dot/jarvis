"""Gesture mouse control: pinch-to-drag windows/widgets across all monitors.

Uses the tracked hand's index fingertip as a virtual pointer mapped onto the
full multi-monitor virtual desktop (screeninfo), and a thumb-index pinch as
left-button press/hold/release (pynput). Pinch a window's title bar and move
your hand to drag it to another monitor.

Off by default; toggled from the HUD or POST /api/gesture. Runs in its own
thread polling the VisionEngine's latest telemetry.
"""

import threading
import time

from .config import settings

# Fraction of camera frame used as the active control region; hand movement
# inside this region maps to the full virtual desktop.
REGION_MIN = 0.15
REGION_MAX = 0.85


class GestureMouse:
    def __init__(self, engine):
        self._engine = engine
        self._enabled = False
        self._thread = None
        self._error = None
        self._mouse = None
        self._button = None
        self._bounds = None  # (min_x, min_y, width, height) of virtual desktop
        self._sx = None  # smoothed position
        self._sy = None
        self._pressed = False

    # -- public ------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def error(self):
        return self._error

    def set_enabled(self, on: bool):
        if on and not self._enabled:
            try:
                self._init_backend()
            except Exception as exc:  # missing deps, headless session, etc.
                self._error = str(exc)
                return False
            self._error = None
            self._enabled = True
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, daemon=True)
                self._thread.start()
        elif not on:
            self._enabled = False
            self._release()
        return True

    # -- internals -----------------------------------------------------------

    def _init_backend(self):
        from pynput.mouse import Button, Controller
        from screeninfo import get_monitors

        monitors = get_monitors()
        if not monitors:
            raise RuntimeError("No monitors detected.")
        min_x = min(m.x for m in monitors)
        min_y = min(m.y for m in monitors)
        max_x = max(m.x + m.width for m in monitors)
        max_y = max(m.y + m.height for m in monitors)
        self._bounds = (min_x, min_y, max_x - min_x, max_y - min_y)
        self._mouse = Controller()
        self._button = Button.left

    def _pick_hand(self, hands):
        preferred = settings.gesture_hand
        for hand in hands:
            if hand["label"] == preferred:
                return hand
        return hands[0] if hands else None

    def _loop(self):
        alpha = max(0.05, min(1.0, settings.gesture_smoothing))
        while True:
            if not self._enabled:
                time.sleep(0.2)
                continue
            _, tracking = self._engine.snapshot()
            hand = self._pick_hand(tracking.get("hands", []))
            frame_size = tracking.get("frame_size")
            if hand and frame_size:
                fw, fh = frame_size
                nx = hand["index_tip"][0] / max(1, fw)
                ny = hand["index_tip"][1] / max(1, fh)
                # Clamp to active region, then normalize to 0..1
                nx = (min(REGION_MAX, max(REGION_MIN, nx)) - REGION_MIN) / (REGION_MAX - REGION_MIN)
                ny = (min(REGION_MAX, max(REGION_MIN, ny)) - REGION_MIN) / (REGION_MAX - REGION_MIN)
                bx, by, bw, bh = self._bounds
                tx = bx + nx * bw
                ty = by + ny * bh
                if self._sx is None:
                    self._sx, self._sy = tx, ty
                else:
                    self._sx += alpha * (tx - self._sx)
                    self._sy += alpha * (ty - self._sy)
                self._mouse.position = (int(self._sx), int(self._sy))

                pinch = bool(hand.get("pinch"))
                if pinch and not self._pressed:
                    self._mouse.press(self._button)
                    self._pressed = True
                elif not pinch and self._pressed:
                    self._release()
            else:
                self._release()
                self._sx = self._sy = None
            time.sleep(0.02)  # ~50 Hz; tracking updates at camera FPS

    def _release(self):
        if self._pressed and self._mouse:
            try:
                self._mouse.release(self._button)
            except Exception:
                pass
        self._pressed = False
