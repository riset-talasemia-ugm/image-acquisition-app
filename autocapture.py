"""Capture otomatis tingkat 1 (docs/use-case.md UC-13): gerbang kualitas per frame.

Operator tetap menggeser meja dan memutar fokus; aplikasi memotret dan menyimpan
sendiri saat frame lolos semua gerbang, diperiksa berurutan dari yang murah:

1. kosong   : frame tidak kosong/seragam (is_blank_frame)
2. diam     : meja tidak bergerak selama AUTO_STILL_CHECKS pemeriksaan berturut-turut
3. baru     : lapang pandang berbeda dari citra tersimpan terakhir (bukan duplikat, F4)
4. fokus    : puncak fokus terkonfirmasi dan status "baik" (FocusTracker)

Skor CLIP (gerbang 4 di UC-13) berjalan dalam mode bayangan: dihitung dan dicatat
saat simpan seperti capture manual, tetapi tidak memblokir, sampai ambangnya
dikalibrasi dengan label dokter.
"""

import threading

import cv2

from config import AUTO_DUPLICATE_NCC, AUTO_STILL_CHECKS, AUTO_STILL_NCC
from quality import _ncc, is_blank_frame

GATE_LABELS = {
    "kosong": "Ada sel di lapang",
    "diam": "Meja diam",
    "baru": "Lapang baru",
    "fokus": "Fokus baik di puncak",
}


def _small(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (64, 48), interpolation=cv2.INTER_AREA).astype("float32")


class AutoGate:
    def __init__(self):
        self.lock = threading.Lock()
        self.prev_small = None
        self.still_count = 0
        self.saved_small = None   # citra tersimpan terakhir (manual maupun otomatis)

    def note_saved(self, frame):
        with self.lock:
            self.saved_small = _small(frame)

    def evaluate(self, frame, quality):
        """Nilai frame terhadap gerbang. `quality` = hasil analyze_focus untuk frame ini.

        Mengembalikan {"ready", "gates": [{id, label, ok, detail}]}. Gerbang
        sesudah kegagalan pertama tetap dilaporkan sebagai belum dinilai (ok None)
        supaya operator melihat urutan lengkapnya.
        """
        small = _small(frame)
        with self.lock:
            moved = self.prev_small is None or _ncc(self.prev_small, small) < AUTO_STILL_NCC
            self.still_count = 0 if moved else self.still_count + 1
            self.prev_small = small
            still_count = self.still_count
            dup = self.saved_small is not None and _ncc(self.saved_small, small) >= AUTO_DUPLICATE_NCC

        status = (quality or {}).get("status")
        checks = [
            ("kosong", lambda: not is_blank_frame(frame), "Frame kosong atau seragam."),
            ("diam", lambda: still_count >= AUTO_STILL_CHECKS, "Meja masih bergerak, tunggu sebentar."),
            ("baru", lambda: not dup, "Lapang sama dengan citra tersimpan terakhir. Geser meja."),
            ("fokus", lambda: status == "baik",
             "Putar fokus melewati titik tertajam lalu kembali." if status is None
             else f"Fokus {status}, putar fokus ke titik tertajam."),
        ]
        gates, failed = [], False
        for gate_id, check, hint in checks:
            ok = None if failed else bool(check())
            failed = failed or ok is False
            gates.append({"id": gate_id, "label": GATE_LABELS[gate_id], "ok": ok, "detail": hint if ok is False else ""})
        return {"ready": not failed, "gates": gates}


auto_gate = AutoGate()
