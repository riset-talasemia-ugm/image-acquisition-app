"""Blueprint rating_bp: lembar penilaian kualitas citra oleh dokter (F14).

Dokter menilai tiap citra capture di satu folder: layak atau tidak untuk
dianotasi, beserta alasan. Penilaian dibuat buta: UI hanya melihat ID acak,
tanpa nama file (yang memuat inisial pasien) dan tanpa skor otomatis. Hasilnya
dipakai untuk mengkalibrasi gerbang fokus/CLIP capture otomatis (UC-13).

File di folder citra:
- penilaian_citra_id.json : {nama file: ID acak}, dibuat sekali, ditambah bila ada citra baru
- penilaian_citra.csv     : satu baris per penilaian; penilaian ulang menambah baris, yang terakhir berlaku
"""

import csv
import json
import os
import re
import secrets
import threading
from datetime import datetime

import cv2
import numpy as np
from flask import Blueprint, jsonify, request

from utils import frame_to_png_base64

rating_bp = Blueprint("rating", __name__)

RATING_ID_FILE = "penilaian_citra_id.json"
RATING_CSV = "penilaian_citra.csv"
RATING_FIELDS = ["timestamp", "rater", "rating_id", "filename", "verdict", "reasons", "note"]
REASONS = ["Buram", "Pinggir buram", "Sel menumpuk", "Kosong atau jarang", "Artefak atau debu", "Lainnya"]
CAPTURE_PATTERN = re.compile(r"^[a-z0-9\-]+_\d{8}-\d{6}_\d+\.png$", re.IGNORECASE)
_lock = threading.Lock()


def _ids(folder):
    """Peta nama file -> ID acak, ditambah untuk citra capture yang baru muncul."""
    path = os.path.join(folder, RATING_ID_FILE)
    ids = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            ids = json.load(f)
    files = sorted(f for f in os.listdir(folder) if CAPTURE_PATTERN.match(f))
    used = set(ids.values())
    changed = False
    for name in files:
        if name not in ids:
            new_id = secrets.token_hex(3).upper()
            while new_id in used:
                new_id = secrets.token_hex(3).upper()
            ids[name] = new_id
            used.add(new_id)
            changed = True
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ids, f, indent=1, sort_keys=True)
    return {i: n for n, i in ids.items() if n in files}  # ID -> nama file, hanya yang masih ada


def _ratings(folder, rater):
    """Penilaian terakhir per ID oleh penilai ini."""
    path = os.path.join(folder, RATING_CSV)
    latest = {}
    if os.path.isfile(path):
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("rater") == rater:
                    latest[row["rating_id"]] = row
    return latest


def rating_summary(folder):
    """Status penilaian per nama file, dipakai sebelum segmentasi batch.

    Citra dianggap TIDAK LAYAK kalau penilaian terakhir dari salah satu penilai
    adalah "tidak" (konservatif demi kualitas dataset). Mengembalikan
    (set nama file tidak layak, set nama file yang sudah dinilai siapa pun).
    """
    path = os.path.join(folder, RATING_CSV)
    latest = {}  # (rater, filename) -> verdict
    if os.path.isfile(path):
        try:
            with open(path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    latest[(row.get("rater"), row.get("filename"))] = row.get("verdict")
        except OSError:
            pass
    unworthy = {fname for (_, fname), verdict in latest.items() if verdict == "tidak"}
    rated = {fname for (_, fname) in latest}
    return unworthy, rated


def _state(folder, rater):
    ids = _ids(folder)
    rated = _ratings(folder, rater)
    order = sorted(ids)  # ID acak, jadi urutan ini sudah teracak terhadap pasien dan waktu
    return ids, rated, order


def _item(folder, ids, rated, rating_id, order):
    frame = cv2.imdecode(np.fromfile(os.path.join(folder, ids[rating_id]), dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return None
    prev = rated.get(rating_id)
    return {
        "id": rating_id,
        "image": frame_to_png_base64(frame),
        "position": order.index(rating_id) + 1,
        "previous": {"verdict": prev["verdict"], "reasons": [r for r in prev["reasons"].split(";") if r],
                     "note": prev["note"]} if prev else None,
    }


def _check(data):
    folder = (data.get("folder") or "").strip()
    rater = (data.get("rater") or "").strip()
    if not rater:
        return None, None, "Isi nama penilai dulu."
    if not folder or not os.path.isdir(folder):
        return None, None, "Folder citra tidak ditemukan. Pilih folder lagi."
    return folder, rater, None


@rating_bp.route("/api/rating/next", methods=["POST"])
def api_rating_next():
    """Citra berikutnya untuk dinilai. Dengan `id`, buka citra itu (untuk
    Sebelumnya/menilai ulang); tanpa `id`, citra pertama yang belum dinilai."""
    data = request.json or {}
    folder, rater, problem = _check(data)
    if problem:
        return jsonify({"ok": False, "message": problem}), 400
    with _lock:
        ids, rated, order = _state(folder, rater)
    total, done = len(order), sum(1 for i in order if i in rated)
    if not total:
        return jsonify({"ok": False, "message": "Tidak ada citra capture (*.png) di folder ini."}), 400
    wanted = data.get("id")
    if wanted is None:
        wanted = next((i for i in order if i not in rated), None)
    if wanted is None:
        return jsonify({"ok": True, "finished": True, "total": total, "done": done})
    if wanted not in ids:
        return jsonify({"ok": False, "message": "ID citra tidak dikenal."}), 400
    item = _item(folder, ids, rated, wanted, order)
    if item is None:
        return jsonify({"ok": False, "message": "Gagal membaca citra."}), 400
    return jsonify({"ok": True, "finished": False, "total": total, "done": done, "reasons": REASONS, **item})


@rating_bp.route("/api/rating/submit", methods=["POST"])
def api_rating_submit():
    data = request.json or {}
    folder, rater, problem = _check(data)
    if problem:
        return jsonify({"ok": False, "message": problem}), 400
    verdict = data.get("verdict")
    reasons = [r for r in (data.get("reasons") or []) if r in REASONS]
    if verdict not in ("layak", "tidak"):
        return jsonify({"ok": False, "message": "Pilih Layak atau Tidak layak."}), 400
    if verdict == "tidak" and not reasons:
        return jsonify({"ok": False, "message": "Pilih minimal satu alasan tidak layak."}), 400
    with _lock:
        ids = _ids(folder)
        rating_id = data.get("id")
        if rating_id not in ids:
            return jsonify({"ok": False, "message": "ID citra tidak dikenal."}), 400
        path = os.path.join(folder, RATING_CSV)
        is_new = not os.path.exists(path)
        try:
            with open(path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=RATING_FIELDS)
                if is_new:
                    writer.writeheader()
                writer.writerow({
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "rater": rater,
                    "rating_id": rating_id,
                    "filename": ids[rating_id],
                    "verdict": verdict,
                    "reasons": ";".join(reasons if verdict == "tidak" else []),
                    "note": (data.get("note") or "").strip(),
                })
        except OSError as e:
            return jsonify({"ok": False, "message": f"Gagal menyimpan penilaian: {e.strerror or e}"}), 500
    return jsonify({"ok": True})
