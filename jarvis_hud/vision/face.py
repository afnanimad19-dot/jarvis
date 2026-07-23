"""Face tracking with MediaPipe Face Mesh.

Reports presence, a rough head-pose estimate (yaw/pitch from landmark
geometry — coarse but stable, good enough for HUD telemetry), and mouth
openness. Draws the mesh tesselation on the frame.
"""

import mediapipe as mp

mp_face = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles

# Landmark indices (MediaPipe canonical face mesh)
NOSE_TIP = 1
CHIN = 152
FOREHEAD = 10
LEFT_EYE_OUTER = 33
RIGHT_EYE_OUTER = 263
UPPER_LIP = 13
LOWER_LIP = 14


class FaceTracker:
    def __init__(self):
        self._mesh = mp_face.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.5,
        )

    def process(self, frame_bgr, rgb):
        """Detect a face in `rgb`, draw the mesh onto `frame_bgr`.

        Returns a dict of face telemetry, or None if no face detected.
        """
        results = self._mesh.process(rgb)
        if not results.multi_face_landmarks:
            return None

        landmarks = results.multi_face_landmarks[0]
        mp_drawing.draw_landmarks(
            frame_bgr,
            landmarks,
            mp_face.FACEMESH_TESSELATION,
            landmark_drawing_spec=None,
            connection_drawing_spec=mp_styles.get_default_face_mesh_tesselation_style(),
        )

        lm = landmarks.landmark
        nose = lm[NOSE_TIP]
        left_eye = lm[LEFT_EYE_OUTER]
        right_eye = lm[RIGHT_EYE_OUTER]
        chin = lm[CHIN]
        forehead = lm[FOREHEAD]

        eye_mid_x = (left_eye.x + right_eye.x) / 2
        eye_span = abs(right_eye.x - left_eye.x) or 1e-6
        face_height = abs(chin.y - forehead.y) or 1e-6

        # Coarse pose: nose offset relative to face geometry, mapped to degrees.
        yaw = round((nose.x - eye_mid_x) / eye_span * 90, 1)
        face_mid_y = (forehead.y + chin.y) / 2
        pitch = round((nose.y - face_mid_y) / face_height * -90, 1)

        mouth_open = abs(lm[LOWER_LIP].y - lm[UPPER_LIP].y) / face_height

        xs = [p.x for p in lm]
        ys = [p.y for p in lm]
        return {
            "present": True,
            "yaw_deg": yaw,
            "pitch_deg": pitch,
            "mouth_open": round(mouth_open, 3),
            "bbox_norm": [min(xs), min(ys), max(xs), max(ys)],
        }

    def close(self):
        self._mesh.close()
