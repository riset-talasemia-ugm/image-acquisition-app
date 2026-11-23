"""Tes gerbang capture otomatis tingkat 1 (autocapture.py)."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autocapture import AutoGate  # noqa: E402
from config import AUTO_STILL_CHECKS  # noqa: E402

BAIK = {"status": "baik"}


def field(seed):
    """Lapang sintetis bertekstur (bukan kosong); seed beda = lapang beda."""
    rng = np.random.default_rng(seed)
    small = rng.integers(0, 255, (12, 16, 3), dtype=np.uint8)
    return np.kron(small, np.ones((20, 20, 1), dtype=np.uint8))


def gate_state(result):
    return {g["id"]: g["ok"] for g in result["gates"]}


class TestAutoGate(unittest.TestCase):
    def settle(self, gate, frame, quality=BAIK):
        result = None
        for _ in range(AUTO_STILL_CHECKS + 1):
            result = gate.evaluate(frame, quality)
        return result

    def test_lapang_diam_fokus_baik_siap(self):
        self.assertTrue(self.settle(AutoGate(), field(1))["ready"])

    def test_belum_cukup_lama_diam(self):
        gate = AutoGate()
        result = gate.evaluate(field(1), BAIK)
        self.assertFalse(result["ready"])
        self.assertEqual(gate_state(result)["diam"], False)
        self.assertIsNone(gate_state(result)["fokus"])  # gerbang sesudah gagal tidak dinilai

    def test_meja_bergerak(self):
        gate = AutoGate()
        for seed in range(AUTO_STILL_CHECKS + 2):
            result = gate.evaluate(field(seed), BAIK)
        self.assertEqual(gate_state(result)["diam"], False)

    def test_frame_kosong(self):
        result = AutoGate().evaluate(np.full((240, 320, 3), 200, np.uint8), BAIK)
        self.assertEqual(gate_state(result)["kosong"], False)

    def test_duplikat_citra_tersimpan(self):
        gate = AutoGate()
        gate.note_saved(field(1))
        result = self.settle(gate, field(1))
        self.assertEqual(gate_state(result)["baru"], False)
        self.assertTrue(self.settle(gate, field(2))["ready"])  # sesudah geser ke lapang lain

    def test_fokus_belum_terkonfirmasi(self):
        result = self.settle(AutoGate(), field(1), {"status": None})
        self.assertEqual(gate_state(result)["fokus"], False)
        self.assertIn("melewati titik tertajam", result["gates"][-1]["detail"])

    def test_fokus_sedang(self):
        result = self.settle(AutoGate(), field(1), {"status": "sedang"})
        self.assertFalse(result["ready"])


if __name__ == "__main__":
    unittest.main()
