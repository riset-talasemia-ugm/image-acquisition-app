"""
Thalassemia WebApp - Image Acquisition App
Jalankan:
    pip install -r requirements.txt
    python app.py
Lalu buka http://127.0.0.1:5000 di browser.
"""

import base64
import csv
import json
import math
import os
import platform
import random
import re
import sys
import threading
import time
from datetime import datetime

import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template, request

from config import (  # noqa: E402
    FOCUS_BLUR_THRESHOLD,
    BLANK_STD_THRESHOLD,
    FOCUS_TILE_COLS,
    FOCUS_TILE_ROWS,
    FOCUS_TILE_MIN_STD,
    FOCUS_LOW_PERCENTILE,
    FOCUS_PEAK_DROP,
    FOCUS_PEAK_TOL,
    FOCUS_FIELD_CHANGE_NCC,
    FOCUS_REL_GOOD,
    FOCUS_REL_WARN,
    FOCUS_EDGE_RATIO_WARN,
    CLIP_ENABLED,
    CLIP_MODEL_NAME,
    CLIP_PRETRAINED,
    CLIP_CROP_FRAC,
    CLIP_GRID_COLS,
    CLIP_GRID_ROWS,
    _CLIP_DENSITY_PAIR,
    _CLIP_POS_V2,
    _CLIP_NEG_V2,
    OPENCV_DISCONNECT_THRESHOLD,
    LOG_FILENAME,
    RBC_CLASS_LABELS,
    RBC_CLASS_COLORS,
    SEGMENTATION_LOG_FILENAME,
    SEGMENTATION_LOG_FIELDNAMES,
    MODEL_CONFIG_FILENAME,
    MODEL_CONFIG_PATH,
    DEFAULT_LOW_CONFIDENCE_THRESHOLD,
)

from csvlog import _ensure_log_columns, log_capture_csv, save_lock, segmentation_log_lock  # noqa: E402

from quality import (  # noqa: E402
    analyze_focus,
    analyze_focus_safe,
    clip_quality,
    compute_focus_score,
    focus_tracker,
    is_blank_frame,
)

from camera import camera, gen_mjpeg  # noqa: E402
from segmentation import segmentation_bp  # noqa: E402
from utils import frame_to_png_base64, safe_slug  # noqa: E402

app = Flask(__name__)
app.register_blueprint(segmentation_bp)


def next_iteration_from_folder(folder, slug):
    """Tentukan nomor iterasi berikutnya dengan membaca file yang SUDAH ADA di folder tujuan.
    """
    pattern = re.compile(
        rf"^{re.escape(slug)}_\d{{8}}-\d{{6}}_(\d+)\.png$", re.IGNORECASE
    )
    max_iter = 0
    try:
        for fname in os.listdir(folder):
            m = pattern.match(fname)
            if m:
                max_iter = max(max_iter, int(m.group(1)))
    except OSError:
        pass
    return max_iter + 1


def resize_for_save(frame, target_width, target_height):
    """Resize gambar sebelum disimpan."
    """
    if not target_width or not target_height:
        return frame
    h, w = frame.shape[:2]
    target_w, target_h = int(target_width), int(target_height)
    if w <= target_w and h <= target_h:
        return frame
    scale = min(target_w / w, target_h / h)
    new_w = max(1, round(w * scale))
    new_h = max(1, round(h * scale))
    return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)


# ---------------------------------------------------------------------------
# Routes - halaman
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    # Dialog "Pengaturan Driver" cuma didukung Windows+DirectShow -- dipakai
    # template buat sembunyikan tombolnya di OS lain (Linux/toupcam) daripada
    # nampilin tombol yang kalau diklik cuma keluar toast "tidak didukung".
    return render_template("index.html", is_windows=(os.name == "nt"))


# ---------------------------------------------------------------------------
# Routes - API kamera
# ---------------------------------------------------------------------------
@app.route("/api/cameras")
def api_cameras():
    return jsonify(camera.list_cameras())


@app.route("/api/camera/connect", methods=["POST"])
def api_camera_connect():
    data = request.json or {}
    index = int(data.get("index", 0))
    width = data.get("width")
    height = data.get("height")
    result = camera.open(index, width, height)
    return jsonify({
        "connected": result["ok"],
        "index": index,
        "width": result.get("width"),
        "height": result.get("height"),
        "message": result.get("message"),
    })


@app.route("/api/camera/settings", methods=["POST"])
def api_camera_settings():
    """Buka dialog properti native driver kamera (lihat CameraManager.open_settings_dialog).
    Dialog ini modal -- request bakal nge-hold sampai user menutup jendelanya."""
    return jsonify(camera.open_settings_dialog())


@app.route("/api/camera/status")
def api_camera_status():
    connected = camera.is_connected()
    return jsonify({
        "connected": connected,
        "index": camera.current_index if connected else None,
        "width": camera.current_width if connected else None,
        "height": camera.current_height if connected else None,
    })


@app.route("/stream")
def stream():
    return Response(gen_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")


# ---------------------------------------------------------------------------
# Routes - capture & save
# ---------------------------------------------------------------------------
@app.route("/api/capture", methods=["POST"])
def api_capture():
    frame = camera.capture()
    if frame is None:
        return jsonify({"ok": False, "message": "Belum ada frame dari kamera."}), 400
    b64 = frame_to_png_base64(frame)
    focus_score = camera.captured_focus_score

    # Analisis kualitas seluruh frame (peak-hold per tile). Skor CLIP (~1,2 dtk)
    # sengaja tidak dihitung di sini supaya gambar cepat tampil; frontend
    # memintanya lewat /api/capture/clip setelah gambar muncul.
    quality = analyze_focus_safe(frame)
    quality["laplacian"] = round(focus_score, 1)
    clip_quality.ensure_started()
    camera.captured_quality = quality
    capture_id = camera.capture_seq

    return jsonify({
        "ok": True,
        "captureId": capture_id,
        "image": b64,
        # focusScore/focusLabel = variance Laplacian lama, dipertahankan untuk
        # pembanding; penilaian utama sekarang ada di "quality".
        "focusScore": round(focus_score, 1),
        "focusLabel": "Baik" if focus_score >= FOCUS_BLUR_THRESHOLD else "Buram",
        "blankWarning": is_blank_frame(frame),
        "quality": quality,
        "semantic": None,
        "clipState": clip_quality.state,
    })


@app.route("/api/capture/clip", methods=["POST"])
def api_capture_clip():
    """Skor CLIP untuk capture terakhir, dipanggil setelah gambar tampil."""
    capture_id = (request.json or {}).get("captureId")
    frame = camera.captured_frame
    if frame is None or capture_id != camera.capture_seq:
        return jsonify({"ok": False, "stale": True})
    # Frame hitam/seragam memberi skor CLIP yang menyesatkan (gabungan_v2 ~0,58
    # pada gambar hitam, sama dengan frame nyata), jadi dilewati.
    if is_blank_frame(frame):
        camera.captured_semantic = None
        return jsonify({"ok": True, "semantic": None, "clipState": clip_quality.state, "blank": True})
    semantic = clip_quality.score(frame)
    if capture_id != camera.capture_seq:   # ada capture baru selama menghitung
        return jsonify({"ok": False, "stale": True})
    camera.captured_semantic = semantic
    return jsonify({"ok": True, "semantic": semantic, "clipState": clip_quality.state})


@app.route("/api/focus/live")
def api_focus_live():
    """Kualitas fokus seluruh frame pada frame terbaru (dipoll UI ~1,5x/detik)."""
    if not camera.is_connected():
        return jsonify({"ok": False, "message": "Kamera belum terhubung."})
    with camera.lock:
        frame = camera.last_frame
    if frame is None:
        return jsonify({"ok": False, "message": "Belum ada frame."})
    clip_quality.ensure_started()
    quality = analyze_focus_safe(frame)
    # Variance Laplacian (metode lama) ikut ditampilkan sebagai pembanding live.
    quality["laplacian"] = round(compute_focus_score(frame), 1)
    return jsonify({"ok": True, "quality": quality, "clipState": clip_quality.state})


@app.route("/api/focus/reset-peak", methods=["POST"])
def api_focus_reset_peak():
    """Buang referensi puncak (mis. saat pindah lapang pandang secara manual)."""
    focus_tracker.reset()
    return jsonify({"ok": True})


@app.route("/api/quality/status")
def api_quality_status():
    return jsonify({
        "clip": {
            "state": clip_quality.state,
            "error": clip_quality.error,
            "model": f"{CLIP_MODEL_NAME}/{CLIP_PRETRAINED}",
        },
        "focus": {
            "cols": FOCUS_TILE_COLS,
            "rows": FOCUS_TILE_ROWS,
            "relGood": FOCUS_REL_GOOD,
            "relWarn": FOCUS_REL_WARN,
            "edgeRatioWarn": FOCUS_EDGE_RATIO_WARN,
        },
    })


@app.route("/api/select-folder", methods=["POST"])
def api_select_folder():
    """Buka dialog folder NATIVE lewat tkinter."""
    result = {"path": None}

    def open_dialog():
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        result["path"] = filedialog.askdirectory(title="Pilih Lokasi Penyimpanan")
        root.destroy()

    t = threading.Thread(target=open_dialog)
    t.start()
    t.join()

    if not result["path"]:
        return jsonify({"ok": False}), 400
    return jsonify({"ok": True, "path": result["path"]})


@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.json or {}
    patient_name = (data.get("patientName") or "").strip()
    folder = (data.get("folder") or "").strip()
    camera_name = (data.get("cameraName") or "").strip()
    target_width = data.get("width")
    target_height = data.get("height")

    if not patient_name:
        return jsonify({"ok": False, "message": "Nama pasien belum diisi."}), 400
    if not folder or not os.path.isdir(folder):
        return jsonify({"ok": False, "message": "Lokasi penyimpanan belum valid."}), 400
    if camera.captured_frame is None:
        return jsonify({"ok": False, "message": "Belum ada gambar yang di-capture."}), 400

    # Skor CLIP dihitung terpisah setelah Capture; kalau Save datang sebelum
    # selesai, hitung di sini supaya log tidak kosong.
    if (camera.captured_semantic is None and clip_quality.state == "ready"
            and not is_blank_frame(camera.captured_frame)):
        seq = camera.capture_seq
        semantic = clip_quality.score(camera.captured_frame)
        if seq == camera.capture_seq:
            camera.captured_semantic = semantic

    slug = safe_slug(patient_name)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Semua langkah di bawah ini (hitung iterasi berikutnya dari isi folder,
    # tulis file gambar, tulis baris log CSV) harus jadi satu unit atomik --
    # kalau dua request /api/save nyaris bersamaan (Flask threaded=True)
    # jalan tanpa lock ini, keduanya bisa saja baca "iterasi berikutnya" yang
    # sama sebelum salah satu selesai menulis, jadi filename ketimpa/duplikat
    # atau baris CSV keselip/korup.
    with save_lock:
        iterasi = next_iteration_from_folder(folder, slug)

        # Kalau kamera tidak bisa diatur resolusinya langsung (mis. MiiCam),
        # ini fallback: kecilin gambar secara software persis sebelum disimpan.
        frame_to_save = resize_for_save(camera.captured_frame, target_width, target_height)

        filename = f"{slug}_{timestamp}_{iterasi:02d}.png"
        full_path = os.path.join(folder, filename)

        ok = cv2.imwrite(full_path, frame_to_save)
        if not ok:
            return jsonify({"ok": False, "message": "Gagal menyimpan file."}), 500

        height, width = frame_to_save.shape[:2]
        quality = camera.captured_quality or {}
        semantic = camera.captured_semantic or {}

        def _fmt(value, digits):
            return "" if value is None else round(value, digits)

        tiles = quality.get("tiles")
        log_capture_csv(folder, {
            "timestamp": timestamp,
            "patient_id": slug,
            "filename": filename,
            "iterasi": iterasi,
            "camera": camera_name or "?",
            "resolution": f"{width}x{height}",
            "focus_score": round(camera.captured_focus_score or 0, 1),
            "tile_median": _fmt(quality.get("median"), 2),
            "tile_low": _fmt(quality.get("low"), 2),
            "tile_center": _fmt(quality.get("center"), 2),
            "tile_edge": _fmt(quality.get("edge"), 2),
            "tile_valid_frac": _fmt(quality.get("validFrac"), 3),
            "edge_ratio": _fmt(quality.get("edgeRatio"), 3),
            "edge_warn": "" if quality.get("edgeWarn") is None else int(bool(quality["edgeWarn"])),
            "rel_low": _fmt(quality.get("relLow"), 3),
            "rel_median": _fmt(quality.get("relMedian"), 3),
            "focus_status": quality.get("status") or "",
            "tile_map_json": json.dumps(tiles, separators=(",", ":")) if tiles else "",
            "clip_kepadatan": _fmt(semantic.get("kepadatan"), 4),
            "clip_gabungan_v2": _fmt(semantic.get("gabungan_v2"), 4),
            "clip_norm": _fmt(semantic.get("norm"), 3),
            "clip_model": semantic.get("model") or "",
        })

    return jsonify(
        {
            "ok": True,
            "filename": filename,
            "path": full_path,
            "count": iterasi,
            "width": width,
            "height": height,
        }
    )


@app.route("/api/folder-summary")
def api_folder_summary():
    """Ringkasan jumlah gambar per pasien di folder tujuan, dibaca langsung
    dari nama file yang ada (bukan dari memori/log), jadi selalu akurat."""
    folder = (request.args.get("folder") or "").strip()
    if not folder or not os.path.isdir(folder):
        return jsonify({"ok": False, "message": "Folder tidak valid."}), 400

    pattern = re.compile(r"^([a-z0-9\-]+)_\d{8}-\d{6}_(\d+)\.png$", re.IGNORECASE)
    counts = {}
    for fname in os.listdir(folder):
        m = pattern.match(fname)
        if m:
            slug = m.group(1)
            counts[slug] = counts.get(slug, 0) + 1

    summary = [{"id": k, "count": v} for k, v in sorted(counts.items())]
    return jsonify({
        "ok": True,
        "summary": summary,
        "totalPatients": len(summary),
        "totalFiles": sum(counts.values()),
    })


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
