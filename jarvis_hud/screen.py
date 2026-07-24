"""Screen capture (mss) — lets JARVIS look at your monitors on request.

monitor=0 captures the full virtual desktop (all monitors side by side);
monitor=1..n captures a single display.
"""


def capture_jpeg(monitor: int = 0, max_width: int = 1680, quality: int = 70) -> bytes:
    try:
        import mss
    except ImportError as exc:
        raise RuntimeError("Screen capture needs mss: pip install mss") from exc
    import cv2
    import numpy as np

    with mss.mss() as sct:
        monitors = sct.monitors  # [0] = all combined, then one entry per display
        idx = monitor if 0 <= monitor < len(monitors) else 0
        shot = sct.grab(monitors[idx])
        img = np.frombuffer(shot.rgb, dtype=np.uint8).reshape(shot.height, shot.width, 3)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    h, w = img.shape[:2]
    if w > max_width:
        img = cv2.resize(img, (max_width, int(h * max_width / w)))
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("Failed to encode screen capture.")
    return buf.tobytes()


def monitor_count() -> int:
    try:
        import mss

        with mss.mss() as sct:
            return max(0, len(sct.monitors) - 1)
    except Exception:
        return 0
