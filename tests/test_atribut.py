"""Tes atribut sel dan kelas turunan (attributes.py), persiapan model multi-label.

Kasus mengikuti tabel Pemetaan kelas di ../tambahan-dataset/README.md.
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from attributes import clean, derived_class_index  # noqa: E402
from config import RBC_CLASS_LABELS  # noqa: E402
from segmentation.mock_model import generate_mock_instance_segmentation  # noqa: E402


def label(ukuran=None, warna="normokrom", bentuk=()):
    return RBC_CLASS_LABELS[derived_class_index({"ukuran": ukuran, "warna": warna, "bentuk": list(bentuk)})]


class TestKelasTurunan(unittest.TestCase):
    def test_tabel_pemetaan(self):
        self.assertEqual(label("normosit"), "Normal cell")
        self.assertEqual(label("mikrosit"), "Microcyte")
        self.assertEqual(label("makrosit"), "Macrocyte")
        self.assertEqual(label(None, "hipokrom"), "Hypochromia")
        # hipokrom kalah dari bentuk selain ovalosit/ellips
        self.assertEqual(label("mikrosit", "hipokrom", ["Target"]), "Target cell")
        # hipokrom menang atas ovalosit dan ellips
        self.assertEqual(label("normosit", "hipokrom", ["Ovalocyte"]), "Hypochromia")
        self.assertEqual(label(None, "normokrom", ["Elliptocyte"]), "Elliptocyte")
        # bentuk menang atas ukuran
        self.assertEqual(label("mikrosit", "normokrom", ["Spherocyte"]), "Spherocyte")

    def test_kelas_dataset_yang_belum_ada_di_aplikasi(self):
        # Microcytic Hypochromia (15) -> Hypochromia; Bite/Blister (13/14) -> Schistocyte (sementara)
        self.assertEqual(label("mikrosit", "hipokrom"), "Hypochromia")
        self.assertEqual(label("normosit", "normokrom", ["Bite"]), "Schistocyte")
        self.assertEqual(label("normosit", "normokrom", ["Blister"]), "Schistocyte")

    def test_clean(self):
        self.assertEqual(
            clean({"ukuran": "raksasa", "warna": "hipokrom", "bentuk": ["Target", "Target", "Kotak"]}),
            {"ukuran": None, "warna": "hipokrom", "bentuk": ["Target"]},
        )
        self.assertIsNone(clean("bukan dict"))

    def test_mock_atribut_konsisten(self):
        frame = np.zeros((240, 320, 3), np.uint8)
        dets = generate_mock_instance_segmentation(frame, "attributes")
        for d in dets:
            self.assertEqual(d["classIndex"], derived_class_index(d["attributes"]))
            self.assertEqual(d["classLabel"], RBC_CLASS_LABELS[d["classIndex"]])
        self.assertNotIn("attributes", generate_mock_instance_segmentation(frame)[0])

    def test_endpoint(self):
        client = app.test_client()
        vocab = client.get("/api/segmentation/attributes").get_json()
        self.assertIn("hipokrom", vocab["warna"])
        res = client.post("/api/segmentation/attributes",
                          json={"attributes": {"ukuran": "mikrosit", "warna": "normokrom", "bentuk": []}}).get_json()
        self.assertEqual(res["classLabel"], "Microcyte")


if __name__ == "__main__":
    unittest.main()
