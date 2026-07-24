"""Vision subsystem: camera capture + MediaPipe hand/face tracking."""

import os

# Quiet MediaPipe/TensorFlow startup noise (harmless W0000 / XNNPACK lines).
# Must be set before mediapipe is imported by the tracker modules.
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
