"""Optional object detection (what is being held) via Ultralytics YOLO.

Disabled by default (JARVIS_ENABLE_OBJECTS=1 to enable) because it pulls in
torch. When enabled, runs YOLOv8-nano every few frames and flags detections
whose box overlaps a detected hand as "held".
"""

import cv2


class ObjectDetector:
    def __init__(self, every_n_frames: int = 10):
        from ultralytics import YOLO  # heavy import, deliberate lazy load

        self._model = YOLO("yolov8n.pt")
        self._every = max(1, every_n_frames)
        self._counter = 0
        self._last = []

    def process(self, frame_bgr, hands):
        self._counter += 1
        if self._counter % self._every == 0:
            self._last = self._detect(frame_bgr)
        h, w = frame_bgr.shape[:2]
        hand_boxes = [hand["bbox_norm"] for hand in hands]
        objects = []
        for det in self._last:
            x1, y1, x2, y2 = det["bbox_norm"]
            held = any(_overlap((x1, y1, x2, y2), hb) for hb in hand_boxes)
            objects.append({**det, "held": held})
            color = (0, 200, 255) if held else (120, 120, 120)
            cv2.rectangle(
                frame_bgr, (int(x1 * w), int(y1 * h)), (int(x2 * w), int(y2 * h)), color, 2
            )
            cv2.putText(
                frame_bgr,
                det["label"],
                (int(x1 * w), max(12, int(y1 * h) - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
            )
        return objects

    def _detect(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        results = self._model.predict(frame_bgr, verbose=False, conf=0.45)
        out = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                out.append(
                    {
                        "label": r.names[int(box.cls[0])],
                        "conf": round(float(box.conf[0]), 2),
                        "bbox_norm": [x1 / w, y1 / h, x2 / w, y2 / h],
                    }
                )
        return out


def _overlap(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return not (ax2 < bx1 or bx2 < ax1 or ay2 < by1 or by2 < ay1)
