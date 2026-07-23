"""Hand tracking with MediaPipe Hands.

Adapted from the owner's original hand_tracking.py prototype: same landmark
model, same finger-counting heuristic, repackaged as a class that returns
structured data instead of running its own window loop.
"""

import cv2
import mediapipe as mp

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles

FINGERTIPS = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}


def count_fingers_up(hand_landmarks, handedness_label):
    """Simple finger-counting: returns how many fingers are extended."""
    lm = hand_landmarks.landmark
    up = 0

    # Four fingers: tip is higher (smaller y) than the joint below it = finger up
    for tip_id in [8, 12, 16, 20]:
        if lm[tip_id].y < lm[tip_id - 2].y:
            up += 1

    # Thumb: compare left/right (x) depending on which hand it is
    if handedness_label == "Right":
        if lm[4].x < lm[3].x:
            up += 1
    else:
        if lm[4].x > lm[3].x:
            up += 1

    return up


GESTURES = {0: "fist", 1: "point", 2: "peace", 3: "three", 4: "four", 5: "open palm"}


class HandTracker:
    def __init__(self, max_hands: int = 2):
        self._hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            model_complexity=0,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5,
        )

    def process(self, frame_bgr, rgb):
        """Detect hands in `rgb`, draw overlays onto `frame_bgr`.

        Returns a list of dicts, one per detected hand.
        """
        h, w = frame_bgr.shape[:2]
        results = self._hands.process(rgb)
        hands = []

        if results.multi_hand_landmarks and results.multi_handedness:
            for hand_landmarks, handedness in zip(
                results.multi_hand_landmarks, results.multi_handedness
            ):
                label = handedness.classification[0].label  # "Left" or "Right"

                mp_drawing.draw_landmarks(
                    frame_bgr,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_styles.get_default_hand_landmarks_style(),
                    mp_styles.get_default_hand_connections_style(),
                )

                tip = hand_landmarks.landmark[FINGERTIPS["index"]]
                tip_x, tip_y = int(tip.x * w), int(tip.y * h)
                fingers = count_fingers_up(hand_landmarks, label)

                xs = [p.x for p in hand_landmarks.landmark]
                ys = [p.y for p in hand_landmarks.landmark]
                hands.append(
                    {
                        "label": label,
                        "fingers_up": fingers,
                        "gesture": GESTURES.get(fingers, "unknown"),
                        "index_tip": [tip_x, tip_y],
                        "bbox_norm": [min(xs), min(ys), max(xs), max(ys)],
                    }
                )
                cv2.circle(frame_bgr, (tip_x, tip_y), 6, (255, 200, 0), -1)

        return hands

    def close(self):
        self._hands.close()
