"""Local camera utilities for A.V.I.

This version intentionally does not perform identity recognition. It can test
camera availability and capture a frame locally; identity recognition can be
added later with explicit enrollment and local storage.
"""
from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime


def camera_status() -> str:
    try:
        import cv2
    except ImportError:
        return "Camera support needs OpenCV. Install it with: pip install opencv-python"
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if os.name == "nt" else 0)
    try:
        if not cap.isOpened():
            return "I couldn't access the default camera."
        ok, _ = cap.read()
        return "The default camera is available." if ok else "The camera opened but did not return a frame."
    finally:
        cap.release()


def capture_camera_frame(path: str = "") -> str:
    try:
        import cv2
    except ImportError:
        return "Camera support needs OpenCV. Install it with: pip install opencv-python"
    target = Path(path).expanduser().resolve() if path else Path(__file__).resolve().parent.parent / "generated" / f"camera_{datetime.now():%Y%m%d_%H%M%S}.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if os.name == "nt" else 0)
    try:
        if not cap.isOpened():
            return "I couldn't access the default camera."
        ok, frame = cap.read()
        if not ok:
            return "I couldn't capture a camera frame."
        cv2.imwrite(str(target), frame)
        return f"Camera frame saved to {target}."
    finally:
        cap.release()
