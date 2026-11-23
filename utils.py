"""Helper kecil yang dipakai capture dan segmentasi."""

import base64
import re

import cv2


def frame_to_png_base64(frame):
    ok, buf = cv2.imencode(".png", frame)
    if not ok:
        return None
    return base64.b64encode(buf.tobytes()).decode("ascii")


def safe_slug(name):
    name = name.strip().lower().replace(" ", "-")
    name = re.sub(r"[^a-z0-9\-]", "", name)
    return name or "pasien"
