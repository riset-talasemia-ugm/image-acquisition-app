"""Tes perbaikan galat sesudah v0.2.0: penyebab gagal simpan dan kamera beku."""
import os
import sys
import tempfile
import time
import unittest

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from camera import CameraManager, camera  # noqa: E402
from capture import write_png  # noqa: E402


def noisy_frame(seed=0):
    return np.random.default_rng(seed).integers(0, 255, (120, 160, 3), dtype=np.uint8)


class TestWritePng(unittest.TestCase):
    def test_folder_non_ascii(self):
        # cv2.imwrite gagal diam-diam untuk path seperti ini di Windows.
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "pasien-é-测试")
            os.makedirs(folder)
            path = os.path.join(folder, "a.png")
            frame = noisy_frame()
            self.assertIsNone(write_png(path, frame))
            back = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
            self.assertTrue(np.array_equal(back, frame))

    def test_folder_hilang(self):
        problem = write_png(os.path.join(tempfile.gettempdir(), "tidak-ada-xyz", "a.png"), noisy_frame())
        self.assertEqual(problem["code"], "folder")

    def test_api_save_folder_hilang(self):
        camera.captured_frame = noisy_frame()
        try:
            res = app.test_client().post("/api/save", json={"patientName": "x", "folder": "Z:/tidak/ada"})
        finally:
            camera.captured_frame = None
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()["code"], "folder")
        self.assertIn("tidak ditemukan", res.get_json()["message"])


class TestKameraBeku(unittest.TestCase):
    def make(self):
        cam = CameraManager()
        cam.is_connected = lambda: True
        return cam

    def test_frame_sama_terus_dianggap_beku(self):
        cam = self.make()
        frame = noisy_frame()
        cam._note_frame_locked(frame)
        cam._last_change_time -= 10
        cam._note_frame_locked(frame)
        self.assertTrue(cam.is_frozen())

    def test_frame_berubah_tidak_beku(self):
        cam = self.make()
        cam._note_frame_locked(noisy_frame(0))
        cam._last_change_time -= 10
        cam._note_frame_locked(noisy_frame(1))
        self.assertFalse(cam.is_frozen())

    def test_frame_gelap_seragam_tidak_beku(self):
        cam = self.make()
        dark = np.zeros((120, 160, 3), np.uint8)
        cam._note_frame_locked(dark)
        cam._last_change_time -= 10
        cam._note_frame_locked(dark)
        self.assertFalse(cam.is_frozen())

    def test_tidak_ada_yang_membaca(self):
        cam = self.make()
        frame = noisy_frame()
        cam._note_frame_locked(frame)
        cam._last_change_time = cam._last_read_time = time.monotonic() - 10
        self.assertFalse(cam.is_frozen())


if __name__ == "__main__":
    unittest.main()
