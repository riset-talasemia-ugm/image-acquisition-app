"""Blueprint capture_bp: kamera, stream, capture, kualitas fokus, pilih folder, simpan, ringkasan folder."""

import json
import os
import re
import shutil
import threading
from datetime import datetime

import cv2
from flask import Blueprint, Response, jsonify, request

from autocapture import auto_gate
from camera import camera, gen_mjpeg
from config import (
    CLIP_MODEL_NAME,
    CLIP_PRETRAINED,
    FOCUS_BLUR_THRESHOLD,
    FOCUS_EDGE_RATIO_WARN,
    FOCUS_REL_GOOD,
    FOCUS_REL_WARN,
    FOCUS_TILE_COLS,
    FOCUS_TILE_ROWS,
    SAVE_MIN_FREE_BYTES,
)
from csvlog import log_capture_csv, save_lock
from quality import analyze_focus_safe, clip_quality, compute_focus_score, focus_tracker, is_blank_frame
from utils import frame_to_png_base64, safe_slug

# Path route ditulis lengkap di tiap decorator (tanpa url_prefix), sama persis dengan v0.1.0.
capture_bp = Blueprint("capture", __name__)


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
# Routes - API kamera
# ---------------------------------------------------------------------------
@capture_bp.route("/api/cameras")
def api_cameras():
    return jsonify(camera.list_cameras())


@capture_bp.route("/api/camera/connect", methods=["POST"])
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


@capture_bp.route("/api/camera/settings", methods=["POST"])
def api_camera_settings():
    """Buka dialog properti native driver kamera (lihat CameraManager.open_settings_dialog).
    Dialog ini modal -- request bakal nge-hold sampai user menutup jendelanya."""
    return jsonify(camera.open_settings_dialog())


@capture_bp.route("/api/camera/status")
def api_camera_status():
    connected = camera.is_connected()
    return jsonify({
        "connected": connected,
        "index": camera.current_index if connected else None,
        "width": camera.current_width if connected else None,
        "height": camera.current_height if connected else None,
        "frozen": camera.is_frozen(),
    })


@capture_bp.route("/stream")
def stream():
    return Response(gen_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")


# ---------------------------------------------------------------------------
# Routes - capture & save
# ---------------------------------------------------------------------------
@capture_bp.route("/api/capture", methods=["POST"])
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


@capture_bp.route("/api/capture/clip", methods=["POST"])
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


@capture_bp.route("/api/focus/live")
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
    result = {"ok": True, "quality": quality, "clipState": clip_quality.state}
    # Capture otomatis menilai gerbangnya di frame yang sama, supaya frame tidak
    # dianalisis dua kali (lihat autocapture.py).
    if request.args.get("auto") == "1":
        result["auto"] = auto_gate.evaluate(frame, quality)
    return jsonify(result)


@capture_bp.route("/api/focus/reset-peak", methods=["POST"])
def api_focus_reset_peak():
    """Buang referensi puncak (mis. saat pindah lapang pandang secara manual)."""
    focus_tracker.reset()
    return jsonify({"ok": True})


@capture_bp.route("/api/quality/status")
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


@capture_bp.route("/api/select-folder", methods=["POST"])
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


@capture_bp.route("/api/save", methods=["POST"])
def api_save():
    data = request.json or {}
    patient_name = (data.get("patientName") or "").strip()
    folder = (data.get("folder") or "").strip()
    camera_name = (data.get("cameraName") or "").strip()
    target_width = data.get("width")
    target_height = data.get("height")
    capture_mode = "otomatis-1" if data.get("mode") == "otomatis" else "manual"

    if not patient_name:
        return jsonify({"ok": False, "message": "Nama pasien belum diisi."}), 400
    if not folder:
        return jsonify({"ok": False, "code": "folder", "message": "Lokasi penyimpanan belum dipilih."}), 400
    if not os.path.isdir(folder):
        return jsonify({
            "ok": False, "code": "folder",
            "message": f"Folder simpan tidak ditemukan ({folder}). Mungkin flashdisk dicabut atau folder "
                       "dipindah/dihapus. Pilih lokasi simpan lagi.",
        }), 400
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

        problem = write_png(full_path, frame_to_save)
        if problem:
            return jsonify({"ok": False, **problem}), 500
        auto_gate.note_saved(camera.captured_frame)  # gerbang "lapang baru" untuk capture otomatis

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
            "capture_mode": capture_mode,
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


def write_png(path, frame):
    """Tulis frame sebagai PNG. Mengembalikan None kalau berhasil, atau
    {"code", "message"} yang menyebut penyebab dan langkah berikutnya.

    Pakai imencode + open() alih-alih cv2.imwrite: isi PNG sama, tetapi
    imwrite gagal diam-diam (cuma False) untuk path non-ASCII di Windows dan
    tidak pernah memberi tahu kenapa gagal.
    """
    folder = os.path.dirname(path)
    ok, buf = cv2.imencode(".png", frame)
    if not ok:
        return {"code": "encode", "message": "Gagal mengubah citra ke PNG. Coba ambil citra lagi."}
    if not os.path.isdir(folder):
        return {"code": "folder", "message": "Folder simpan hilang (flashdisk dicabut atau folder dipindah). Pilih lokasi simpan lagi."}
    try:
        free = shutil.disk_usage(folder).free
    except OSError:
        free = None
    if free is not None and free < len(buf) + SAVE_MIN_FREE_BYTES:
        return {
            "code": "disk_full",
            "message": f"Ruang disk hampir penuh (sisa {free // (1024 * 1024)} MB). "
                       "Kosongkan disk atau pilih lokasi simpan lain.",
        }
    if not os.access(folder, os.W_OK):
        return {"code": "permission", "message": "Tidak punya izin menulis ke folder ini. Pilih lokasi simpan lain."}
    try:
        with open(path, "wb") as f:
            f.write(buf.tobytes())
    except OSError as e:
        # File setengah jadi jangan ditinggal: iterasi berikutnya dihitung dari isi folder.
        try:
            os.remove(path)
        except OSError:
            pass
        reason = {28: "disk penuh", 13: "izin ditolak", 2: "folder hilang"}.get(e.errno, e.strerror or str(e))
        return {"code": "write", "message": f"Gagal menulis file ({reason}). Cek folder simpan, lalu coba simpan lagi."}
    return None


@capture_bp.route("/api/folder-summary")
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
