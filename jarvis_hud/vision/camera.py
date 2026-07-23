"""Camera capture + tracking loop running in a background thread.

Keeps the latest annotated JPEG frame and tracking telemetry available to
the web server under a lock. The Iriun webcam shows up as a regular OS
camera device, so plain cv2.VideoCapture works.
"""

import platform
import threading
import time

import cv2

from ..config import settings
from .face import FaceTracker
from .hands import HandTracker


class VisionEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._jpeg = None  # latest annotated frame, JPEG bytes
        self._tracking = {"camera": False, "hands": [], "face": None, "objects": [], "fps": 0}

    # -- public API -------------------------------------------------------

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def snapshot(self):
        """Returns (jpeg_bytes_or_None, tracking_dict)."""
        with self._lock:
            return self._jpeg, dict(self._tracking)

    # -- internals ---------------------------------------------------------

    def _open_camera(self):
        backend = cv2.CAP_AVFOUNDATION if platform.system() == "Darwin" else cv2.CAP_ANY
        cap = cv2.VideoCapture(settings.camera_index, backend)
        if not cap.isOpened():
            cap = cv2.VideoCapture(settings.camera_index)
        return cap if cap.isOpened() else None

    def _loop(self):
        cap = self._open_camera()
        if cap is None:
            with self._lock:
                self._tracking = {
                    "camera": False,
                    "error": (
                        f"Cannot open camera index {settings.camera_index}. "
                        "Try JARVIS_CAMERA_INDEX=1 or 2 (Iriun is often not device 0)."
                    ),
                    "hands": [],
                    "face": None,
                    "objects": [],
                    "fps": 0,
                }
            self._running = False
            return

        hands = HandTracker(max_hands=settings.max_hands)
        face = FaceTracker() if settings.enable_face else None
        objects = None
        if settings.enable_objects:
            try:
                from .objects import ObjectDetector

                objects = ObjectDetector()
            except ImportError:
                print("[JARVIS] ultralytics not installed; object detection disabled.")

        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), settings.jpeg_quality]
        last_time = time.time()
        fps = 0.0

        while self._running:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue

            if settings.flip_camera:
                frame = cv2.flip(frame, 1)

            # Downscale for tracking + streaming
            h, w = frame.shape[:2]
            if w > settings.frame_width:
                scale = settings.frame_width / w
                frame = cv2.resize(frame, (settings.frame_width, int(h * scale)))

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hand_data = hands.process(frame, rgb)
            face_data = face.process(frame, rgb) if face else None
            object_data = objects.process(frame, hand_data) if objects else []

            now = time.time()
            dt = now - last_time
            last_time = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)

            ok, buf = cv2.imencode(".jpg", frame, encode_params)
            with self._lock:
                if ok:
                    self._jpeg = buf.tobytes()
                self._tracking = {
                    "camera": True,
                    "hands": hand_data,
                    "face": face_data,
                    "objects": object_data,
                    "fps": round(fps, 1),
                }

        cap.release()
        hands.close()
        if face:
            face.close()
