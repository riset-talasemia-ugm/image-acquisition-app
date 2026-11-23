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



class TestSesiDanPemulihan(unittest.TestCase):
    def setUp(self):
        import capture
        self.capture = capture
        self.tmp = tempfile.TemporaryDirectory()
        self.orig = (capture.RECOVERY_PNG, capture.RECOVERY_META, capture.RECOVERY_DIR)
        capture.RECOVERY_DIR = self.tmp.name
        capture.RECOVERY_PNG = os.path.join(self.tmp.name, "capture.png")
        capture.RECOVERY_META = os.path.join(self.tmp.name, "capture.json")
        self.client = app.test_client()

    def tearDown(self):
        self.capture.RECOVERY_PNG, self.capture.RECOVERY_META, self.capture.RECOVERY_DIR = self.orig
        camera.captured_frame = None
        self.tmp.cleanup()

    def test_pulihkan_lalu_buang(self):
        from utils import frame_to_png_base64
        frame = noisy_frame()
        self.assertFalse(self.client.get("/api/recovery/capture").get_json()["exists"])
        self.capture._write_recovery(frame_to_png_base64(frame), {"time": "2026-11-23T10:00:00", "quality": None})
        self.assertTrue(self.client.get("/api/recovery/capture").get_json()["exists"])
        res = self.client.post("/api/recovery/capture", json={"action": "restore"}).get_json()
        self.assertTrue(res["ok"])
        self.assertTrue(np.array_equal(camera.captured_frame, frame))
        self.client.post("/api/recovery/capture", json={"action": "discard"})
        self.assertFalse(self.client.get("/api/recovery/capture").get_json()["exists"])

    def test_open_path(self):
        folder = os.path.join(self.tmp.name, "pasien-é")
        os.makedirs(folder)
        path = os.path.join(folder, "a.png")
        write_png(path, noisy_frame())
        res = self.client.post("/api/segmentation/open-path", json={"path": path}).get_json()
        self.assertEqual((res["width"], res["height"]), (160, 120))
        self.assertEqual(self.client.post("/api/segmentation/open-path", json={"path": path + "x"}).status_code, 400)

    def test_system_status(self):
        res = self.client.get("/api/system/status").get_json()
        self.assertFalse(res["clockSuspect"])
        self.assertGreater(res["disk"]["free"], 0)


if __name__ == "__main__":
    unittest.main()
