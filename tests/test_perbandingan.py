"""Tes file perbandingan sistem-dokter (F15), atribut dan tanda koreksi di export."""
import json
import os
import sys
import tempfile
import unittest

import numpy as np
from openpyxl import load_workbook

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from capture import write_png  # noqa: E402
from segmentation.compare import cohen_kappa  # noqa: E402


def det(i, cls, label, **kw):
    d = {"id": i, "classIndex": cls, "classLabel": label, "confidence": 0.9,
         "bbox": [1, 1, 5, 5], "mask": [[1, 1], [5, 1], [5, 5]],
         "correctedClassIndex": None, "correctedClassLabel": None, "doctorVerdict": None}
    d.update(kw)
    return d


class TestPerbandingan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = self.tmp.name
        self.client = app.test_client()
        rng = np.random.default_rng(0)
        # Gambar 1, model kelas tunggal: setuju, dikoreksi, dihapus, ditambah, belum direview.
        p1 = os.path.join(self.folder, "ab-12_20261123-100000_01.png")
        write_png(p1, rng.integers(0, 255, (60, 80, 3), dtype=np.uint8))
        self.save(p1, [
            det(0, 0, "Normal cell", doctorVerdict="correct"),
            det(1, 0, "Normal cell", correctedClassIndex=4, correctedClassLabel="Target cell", doctorVerdict="incorrect"),
            det(2, 2, "Microcyte", deletedByDoctor=True),
            det(3, 10, "Uncategorised", manual=True, correctedClassIndex=1, correctedClassLabel="Macrocyte"),
            det(4, 0, "Normal cell"),
        ])
        # Gambar 2, model atribut, review mode atribut: dokter mengubah warna.
        p2 = os.path.join(self.folder, "ab-12_20261123-100100_02.png")
        write_png(p2, rng.integers(0, 255, (60, 80, 3), dtype=np.uint8))
        model = {"ukuran": "mikrosit", "warna": "normokrom", "bentuk": []}
        self.save(p2, [
            det(0, 2, "Microcyte", attributes=model,
                correctedAttributes={**model, "warna": "hipokrom"}, correctedClassIndex=11,
                correctedClassLabel="Hypochromia", doctorVerdict="incorrect"),
            det(1, 2, "Microcyte", attributes=model, doctorVerdict="correct"),
        ], labelMode="attributes")

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, path, dets, **extra):
        res = self.client.post("/api/segmentation/save",
                               json={"path": path, "patientId": "AB-12", "detections": dets, **extra})
        self.assertTrue(res.get_json()["ok"])

    def test_file_perbandingan(self):
        res = self.client.post("/api/segmentation/export-comparison", json={"folder": self.folder}).get_json()
        self.assertTrue(res["ok"])
        wb = load_workbook(res["path"])
        self.assertEqual(wb.sheetnames, ["Perbandingan", "Ringkasan", "Matriks"])
        values = [v for row in wb["Perbandingan"].iter_rows(values_only=True) for v in row if v is not None]
        for text in ("bukan sel / dihapus", "tidak terdeteksi", "belum direview", "Pendapat Dokter", "hipokrom"):
            self.assertIn(text, values)
        total = [r for r in wb["Ringkasan"].iter_rows(values_only=True) if r and r[0] == "Total batch"][0]
        # dinilai: setuju, dikoreksi, dihapus (gbr 1) + 2 sel gbr 2 = 5; setuju: sel 0 gbr 1 + sel 1 gbr 2
        self.assertEqual(total[2:4], (5, 2))
        self.assertEqual(total[6:9], (1, 1, 6))  # dihapus, ditambah, eritrosit
        matrix = {r[0]: r[1:] for r in wb["Matriks"].iter_rows(min_row=2, values_only=True)}
        header = [c.value for c in wb["Matriks"][1]][1:]
        self.assertEqual(matrix["Microcyte"][header.index("dihapus dokter")], 1)
        self.assertEqual(matrix["ditambah dokter"][header.index("Macrocyte")], 1)

    def test_excel_dan_coco_membawa_atribut_dan_koreksi(self):
        rep = self.client.post("/api/segmentation/export-report", json={"folder": self.folder}).get_json()
        wb = load_workbook(rep["path"])
        koreksi = [r for r in wb["Koreksi per Sel"].iter_rows(min_row=2, values_only=True)]
        self.assertIn("kelas", [r[5] for r in koreksi])
        self.assertIn("kelas, warna", [r[5] for r in koreksi])
        self.assertIn("dihapus", [r[5] for r in koreksi])
        atribut = list(wb["Atribut per Pasien"].iter_rows(min_row=2, values_only=True))[0]
        self.assertEqual(atribut[:3], ("AB-12", 2, 100.0))  # 2 sel beratribut, 100% mikrosit

        coco = self.client.post("/api/segmentation/export-coco", json={"folder": self.folder}).get_json()
        with open(coco["path"], encoding="utf-8") as f:
            anns = json.load(f)["annotations"]
        sources = sorted(a.get("attributes_source", "") for a in anns)
        self.assertIn("dokter", sources)
        self.assertIn("dokter (setuju model)", sources)
        self.assertTrue(any(a.get("added_by_doctor") for a in anns))
        self.assertTrue(any(a.get("corrected_by_doctor") == ["kelas", "warna"] for a in anns))
        self.assertEqual(len(anns), 6)  # sel dihapus dokter tidak ikut

    def test_laporan_menampilkan_atribut(self):
        html = self.client.get("/laporan", query_string={"folder": self.folder, "patient": "AB-12"}).get_data(as_text=True)
        self.assertIn("Atribut sel (ukuran, bentuk, warna)", html)
        self.assertIn("Ukuran mikrosit", html)

    def test_kappa(self):
        self.assertEqual(cohen_kappa([("a", "a"), ("b", "b")]), 1.0)
        self.assertIsNone(cohen_kappa([]))


if __name__ == "__main__":
    unittest.main()
