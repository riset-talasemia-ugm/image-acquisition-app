"""Tes laporan pasien (report.py, UC-07)."""
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from capture import write_png  # noqa: E402
from report import patient_report  # noqa: E402


def det(i, cls, label, corrected=None, verdict=None):
    return {
        "id": i, "classIndex": cls, "classLabel": label, "confidence": 0.9,
        "bbox": [1, 1, 5, 5], "mask": [[1, 1], [5, 1], [5, 5]],
        "correctedClassIndex": corrected[0] if corrected else None,
        "correctedClassLabel": corrected[1] if corrected else None,
        "doctorVerdict": verdict,
    }


class TestLaporan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = self.tmp.name
        self.client = app.test_client()
        path = os.path.join(self.folder, "ab-12_20261123-100000_01.png")
        write_png(path, np.random.default_rng(0).integers(0, 255, (60, 80, 3), dtype=np.uint8))
        dets = [
            det(0, 0, "Normal cell", verdict="correct"),
            det(1, 0, "Normal cell", corrected=(4, "Target cell"), verdict="incorrect"),
            det(2, 10, "Uncategorised"),
        ]
        res = self.client.post("/api/segmentation/save", json={"path": path, "patientId": "AB-12", "detections": dets})
        self.assertTrue(res.get_json()["ok"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_angka_sesudah_koreksi(self):
        r = patient_report(self.folder, "ab-12")  # inisial dicocokkan lewat slug
        counts = {c["label"]: c["n"] for c in r["classes"]}
        self.assertEqual((r["images"], r["total"], r["rbc"]), (1, 3, 2))  # Uncategorised tidak dihitung
        self.assertEqual((counts["Normal cell"], counts["Target cell"]), (1, 1))
        self.assertEqual((r["reviewed"], r["corrected"]), (2, 1))

    def test_halaman_tanpa_nama_file(self):
        res = self.client.get("/laporan", query_string={"folder": self.folder, "patient": "AB-12"})
        html = res.get_data(as_text=True)
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("20261123-100000", html)
        self.assertNotIn(self.folder, html)
        self.assertIn("kurang dari minimal 1.000", html)
        self.assertIn("alat bantu", html)

    def test_parameter_kosong(self):
        self.assertEqual(self.client.get("/laporan").status_code, 400)



class TestSelDihapusDokter(unittest.TestCase):
    def test_tersimpan_tapi_tidak_dihitung(self):
        import csv
        import json
        with tempfile.TemporaryDirectory() as folder:
            client = app.test_client()
            path = os.path.join(folder, "ab-12_20261123-100000_01.png")
            write_png(path, np.random.default_rng(0).integers(0, 255, (60, 80, 3), dtype=np.uint8))
            gone = det(1, 0, "Normal cell")
            gone["deletedByDoctor"] = True
            res = client.post("/api/segmentation/save", json={
                "path": path, "patientId": "AB-12", "detections": [det(0, 0, "Normal cell"), gone]}).get_json()
            self.assertEqual(res["totalCells"], 1)
            with open(os.path.join(folder, "segmentation_log.csv"), newline="", encoding="utf-8") as f:
                row = list(csv.DictReader(f))[-1]
            self.assertEqual(row["total_cells"], "1")
            with open(os.path.join(folder, row["detail_file"]), encoding="utf-8") as f:
                self.assertEqual(len(json.load(f)["detections"]), 2)  # tetap tercatat untuk F15
            self.assertEqual(patient_report(folder, "AB-12")["total"], 1)
            coco = client.post("/api/segmentation/export-coco", json={"folder": folder, "onlyReviewed": False}).get_json()
            self.assertTrue(coco["ok"])
            with open(os.path.join(folder, coco["filename"]), encoding="utf-8") as f:
                self.assertEqual(len(json.load(f)["annotations"]), 1)


if __name__ == "__main__":
    unittest.main()
