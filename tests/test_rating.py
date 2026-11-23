"""Tes lembar penilaian citra (rating.py, F14) dan batch yang melewati citra tidak layak."""
import json
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from capture import write_png  # noqa: E402

FILES = ["ab-12_20261123-100000_01.png", "ab-12_20261123-100100_02.png", "cd-34_20261123-110000_01.png"]


class TestPenilaian(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = self.tmp.name
        rng = np.random.default_rng(0)
        for name in FILES:
            write_png(os.path.join(self.folder, name), rng.integers(0, 255, (60, 80, 3), dtype=np.uint8))
        self.client = app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def next(self, rater="dr. A", **extra):
        return self.client.post("/api/rating/next", json={"folder": self.folder, "rater": rater, **extra})

    def submit(self, rating_id, verdict, reasons=(), rater="dr. A"):
        return self.client.post("/api/rating/submit", json={
            "folder": self.folder, "rater": rater, "id": rating_id, "verdict": verdict, "reasons": list(reasons),
        })

    def test_buta_terhadap_nama_file(self):
        res = self.next()
        body = res.get_data(as_text=True)
        self.assertEqual(res.status_code, 200)
        for name in FILES:
            self.assertNotIn(name, body)
            self.assertNotIn(name.split("_")[0], body)  # inisial pasien
        self.assertEqual(res.get_json()["total"], 3)

    def test_nilai_semua_lalu_selesai(self):
        seen = set()
        for _ in FILES:
            item = self.next().get_json()
            self.assertNotIn(item["id"], seen)
            seen.add(item["id"])
            self.assertEqual(self.submit(item["id"], "layak").status_code, 200)
        done = self.next().get_json()
        self.assertTrue(done["finished"])
        self.assertEqual(done["done"], 3)
        # Penilai lain mulai dari nol.
        self.assertEqual(self.next(rater="dr. B").get_json()["done"], 0)

    def test_tidak_layak_wajib_alasan(self):
        item = self.next().get_json()
        self.assertEqual(self.submit(item["id"], "tidak").status_code, 400)
        self.assertEqual(self.submit(item["id"], "tidak", ["Buram", "bukan-alasan"]).status_code, 200)
        again = self.next(id=item["id"]).get_json()
        self.assertEqual(again["previous"]["reasons"], ["Buram"])

    def test_id_stabil_antar_pemanggilan(self):
        first = self.next().get_json()["id"]
        with open(os.path.join(self.folder, "penilaian_citra_id.json"), encoding="utf-8") as f:
            ids = json.load(f)
        self.assertIn(first, ids.values())
        self.assertEqual(self.next().get_json()["id"], first)

    def test_batch_melewati_citra_tidak_layak(self):
        item = self.next().get_json()
        self.submit(item["id"], "tidak", ["Buram"])
        res = self.client.post("/api/segmentation/batch-run", json={"folder": self.folder}).get_json()
        self.assertEqual(res["totalUnworthy"], 1)
        unworthy = [r["filename"] for r in res["perImage"] if r.get("unworthy")]
        with open(os.path.join(self.folder, "penilaian_citra_id.json"), encoding="utf-8") as f:
            ids = json.load(f)
        self.assertEqual(ids[unworthy[0]], item["id"])
        self.assertEqual(res["totalImagesOk"], 3)  # 2 diproses + 1 dilewati


if __name__ == "__main__":
    unittest.main()
