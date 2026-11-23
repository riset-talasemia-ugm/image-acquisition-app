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

from segmentation import segmentation_bp  # noqa: E402
from segmentation.storage import _latest_segmentation_rows, _load_model_config  # noqa: E402
from utils import frame_to_png_base64, safe_slug  # noqa: E402

app = Flask(__name__)
app.register_blueprint(segmentation_bp)


# ---------------------------------------------------------------------------
# SDK vendor ToupCam (opsional, cuma dipakai di Linux)
# ---------------------------------------------------------------------------
# Beberapa kamera vendor (mis. MiiCam, rebrand dari chipset ToupTek) ternyata
# tidak sepenuhnya UVC-compliant dari sisi yang bisa di-bind modul kernel
# `uvcvideo` standar -- di beberapa board (mis. NVIDIA Jetson) device-nya
# kebaca di level USB tapi gagal dapat /dev/videoN sama sekali. SDK vendor
# (komunikasi langsung ke USB lewat libusb, bypass uvcvideo/V4L2) berhasil
# baca kameranya. Ini loader lazy buat SDK itu.
#
# libtoupcam.so adalah biner native per-arsitektur CPU, jadi dibundel
# per-arsitektur di vendor/toupcam/<arch>/ (masing-masing juga bawa salinan
# toupcam.py sendiri, karena binding-nya cari .so di folder yang sama
# persis dengan dirinya). Arsitektur dideteksi otomatis lewat
# platform.machine() -- tinggal tambah folder arch baru kalau nanti perlu
# platform lain (mis. armhf untuk Raspberry Pi 32-bit).
#
# Cuma dicoba di Linux -- di Windows OpenCV+DirectShow sudah cukup, jadi
# tidak diutak-atik supaya tidak menambah risiko regresi di sana.
_toupcam_sdk_cache = {"loaded": False, "module": None}

_TOUPCAM_ARCH_MAP = {
    "aarch64": "arm64",
    "arm64": "arm64",
    "x86_64": "x64",
    "amd64": "x64",
}


def _load_toupcam_sdk():
    if _toupcam_sdk_cache["loaded"]:
        return _toupcam_sdk_cache["module"]
    _toupcam_sdk_cache["loaded"] = True
    if os.name != "posix":
        return None

    arch_dir = _TOUPCAM_ARCH_MAP.get(platform.machine().lower())
    if arch_dir is None:
        print(f"[DEBUG] ToupCam SDK: arsitektur '{platform.machine()}' belum didukung/dibundel.")
        return None

    vendor_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "vendor", "toupcam", arch_dir
    )
    if not os.path.isfile(os.path.join(vendor_dir, "libtoupcam.so")):
        return None
    try:
        if vendor_dir not in sys.path:
            sys.path.insert(0, vendor_dir)
        import toupcam as toupcam_sdk

        _toupcam_sdk_cache["module"] = toupcam_sdk
        return toupcam_sdk
    except Exception as e:
        print(f"[DEBUG] ToupCam SDK gagal dimuat: {e}")
        return None


# ---------------------------------------------------------------------------
# Camera state
# ---------------------------------------------------------------------------
class CameraManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.backend = None          # "opencv" atau "toupcam", None kalau belum connect
        self.cap = None              # cv2.VideoCapture, dipakai kalau backend == "opencv"
        self.current_index = None    # index tampilan (posisi di list_cameras())
        self.current_width = None    # resolusi aktual kamera yang sedang terhubung
        self.current_height = None
        self.last_frame = None       # frame terakhir dari stream (untuk MJPEG)
        self.captured_frame = None   # frame yang dibekukan lewat tombol Capture
        self.captured_focus_score = None
        self.captured_quality = None    # hasil analyze_focus() untuk captured_frame (diisi api_capture)
        self.captured_semantic = None   # hasil ClipQuality.score() untuk captured_frame, kalau aktif
        self.capture_seq = 0            # nomor capture; hasil CLIP yang terlambat dibuang kalau sudah ada capture baru
        self._registry = []          # hasil list_cameras() terakhir, index -> {backend, ...}

        # State khusus backend ToupCam
        self._tc_handle = None
        self._tc_buf = None
        self._tc_row_pitch = 0
        self._tc_width = 0
        self._tc_height = 0
        self._tc_connected = False
        self._tc_last_pull = 0.0

        # State khusus backend OpenCV -- cv2.VideoCapture.isOpened() TIDAK
        # otomatis jadi False cuma karena kameranya dicabut fisik; harus
        # dideteksi lewat read() yang gagal berkali-kali berturut-turut.
        self._opencv_connected = False
        self._opencv_read_failures = 0

    def list_cameras(self, max_index=5):
        """Daftar kamera yang tersedia, gabungan SDK vendor ToupCam (kalau ada
        kamera yang cuma bisa dibaca lewat situ, mis. MiiCam di Linux) dan
        probe generik OpenCV/pygrabber/V4L2. Hasilnya disimpan di
        self._registry supaya open(index) tahu backend & device id yang tepat
        untuk index yang sama persis dengan yang ditampilkan di sini."""
        registry = []

        toupcam_sdk = _load_toupcam_sdk()
        if toupcam_sdk is not None:
            try:
                devices = toupcam_sdk.Toupcam.EnumV2()
                for dev in devices:
                    registry.append({
                        "name": dev.displayname,
                        "backend": "toupcam",
                        "toupcam_id": dev.id,
                    })
                if devices:
                    print(f"[DEBUG] ToupCam SDK menemukan device: {[d.displayname for d in devices]}")
            except Exception as e:
                print(f"[DEBUG] ToupCam EnumV2 gagal: {e}")

        if os.name == "nt":
            try:
                import comtypes
                try:
                    comtypes.CoInitialize()
                except Exception:
                    pass

                from pygrabber.dshow_graph import FilterGraph

                names = FilterGraph().get_input_devices()
                print(f"[DEBUG] pygrabber menemukan device: {list(enumerate(names))}")
                for i, n in enumerate(names):
                    registry.append({"name": n, "backend": "opencv", "cv_index": i})
            except Exception as e:
                print(f"[DEBUG] pygrabber gagal, fallback ke probe OpenCV: {e}")
                registry.extend(self._probe_opencv_indices(max_index))
        else:
            registry.extend(self._probe_opencv_indices(max_index))

        for i, entry in enumerate(registry):
            entry["index"] = i
        self._registry = registry
        return [{"index": e["index"], "name": e["name"]} for e in registry]

    def _probe_opencv_indices(self, max_index):
        backend = cv2.CAP_DSHOW if os.name == "nt" else 0
        found = []
        for i in range(max_index):
            cap = cv2.VideoCapture(i, backend)
            if cap is not None and cap.isOpened():
                name = f"Kamera USB #{i}"
                if os.name == "posix":
                    name_path = f"/sys/class/video4linux/video{i}/name"
                    try:
                        if os.path.isfile(name_path):
                            with open(name_path, "r") as f:
                                real_name = f.read().strip()
                            if real_name:
                                name = real_name
                    except OSError:
                        pass
                found.append({"name": name, "backend": "opencv", "cv_index": i})
            if cap is not None:
                cap.release()
        return found

    def open(self, index, width=None, height=None):
        """Buka kamera pada index tampilan (hasil list_cameras()). Otomatis
        pilih backend yang sesuai (ToupCam SDK atau OpenCV) berdasarkan
        self._registry."""
        with self.lock:
            entry = self._registry[index] if 0 <= index < len(self._registry) else None
            self._release_locked()

            if entry is not None and entry["backend"] == "toupcam":
                result = self._open_toupcam_locked(entry["toupcam_id"], width, height)
            else:
                cv_index = entry["cv_index"] if entry is not None else index
                result = self._open_opencv_locked(cv_index, width, height)

            self.current_index = index if result.get("ok") else None
            self.current_width = result.get("width") if result.get("ok") else None
            self.current_height = result.get("height") if result.get("ok") else None
            return result

    def _release_locked(self):
        """Lepas backend yang sedang aktif (kalau ada). Harus dipanggil
        dalam keadaan self.lock sudah dipegang."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if self._tc_handle is not None:
            try:
                self._tc_handle.Close()
            except Exception:
                pass
            self._tc_handle = None
        self._tc_connected = False
        self.backend = None

    def _open_opencv_locked(self, cv_index, width, height):
        backend = cv2.CAP_DSHOW if os.name == "nt" else 0
        cap = cv2.VideoCapture(cv_index, backend)
        if not cap.isOpened():
            return {"ok": False}

        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

        if width and height:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.cap = cap
        self.backend = "opencv"
        self._opencv_connected = True
        self._opencv_read_failures = 0
        return {"ok": True, "width": actual_w, "height": actual_h}

    def _open_toupcam_locked(self, cam_id, width, height):
        sdk = _load_toupcam_sdk()
        if sdk is None:
            return {"ok": False, "message": "ToupCam SDK tidak tersedia."}
        try:
            h = sdk.Toupcam.Open(cam_id)
        except Exception as e:
            return {"ok": False, "message": f"Gagal membuka kamera (ToupCam): {e}"}
        if h is None:
            return {"ok": False}

        try:
            # Paksa BGR (default di Linux adalah RGB) biar konsisten dengan
            # OpenCV di sisa aplikasi (imencode/imwrite/cvtColor semua asumsi BGR).
            h.put_Option(sdk.TOUPCAM_OPTION_BYTEORDER, 1)
        except Exception:
            pass

        if width and height:
            try:
                # Sensor ToupCam cuma mendukung daftar resolusi diskrit
                # tertentu (bukan sembarang angka) -- put_Size(width, height)
                # dengan nilai yang bukan salah satu step itu akan ditolak
                # (E_INVALIDARG). Jadi cari dulu resolusi valid TERDEKAT dari
                # daftar yang benar-benar didukung kamera, baru pakai
                # put_eSize(index) buat pilih itu.
                target_w, target_h = int(width), int(height)
                n = h.ResolutionNumber()
                best_idx, best_score = None, None
                for i in range(n):
                    rw, rh = h.get_Resolution(i)
                    score = abs(rw - target_w) + abs(rh - target_h)
                    if best_score is None or score < best_score:
                        best_idx, best_score = i, score
                if best_idx is not None:
                    h.put_eSize(best_idx)
            except Exception as e:
                print(f"[DEBUG] ToupCam set resolusi gagal (lanjut pakai resolusi default): {e}")

        try:
            # RealTime = SDK selalu kirim frame TERBARU dan buang backlog,
            h.put_RealTime(1)
        except Exception:
            pass

        try:
            w, ht = h.get_Size()
        except Exception as e:
            try:
                h.Close()
            except Exception:
                pass
            return {"ok": False, "message": f"Gagal membaca ukuran gambar (ToupCam): {e}"}

        self._tc_handle = h
        self._tc_row_pitch = w * 3
        self._tc_buf = bytes(self._tc_row_pitch * ht)
        self._tc_width = w
        self._tc_height = ht
        self._tc_connected = True
        self._tc_last_pull = 0.0
        self.backend = "toupcam"

        try:
            h.StartPullModeWithCallback(CameraManager._toupcam_event_callback, self)
        except Exception as e:
            self._tc_handle = None
            self._tc_connected = False
            self.backend = None
            try:
                h.Close()
            except Exception:
                pass
            return {"ok": False, "message": f"Gagal memulai stream (ToupCam): {e}"}

        return {"ok": True, "width": w, "height": ht}

    @staticmethod
    def _toupcam_event_callback(nEvent, ctx):
        # Callback ini dipanggil dari thread internal SDK, bukan thread Flask.
        ctx._on_toupcam_event(nEvent)

    def _on_toupcam_event(self, nEvent):
        sdk = _load_toupcam_sdk()
        if sdk is None:
            return
        if nEvent == sdk.TOUPCAM_EVENT_IMAGE:
            # Throttle ke ~20fps.
            now = time.monotonic()
            if now - self._tc_last_pull < 0.05:
                return
            self._tc_last_pull = now
            try:
                with self.lock:
                    if self._tc_handle is None:
                        return
                    self._tc_handle.PullImageV4(self._tc_buf, 0, 24, self._tc_row_pitch, None)
                    frame = np.frombuffer(self._tc_buf, dtype=np.uint8).reshape(
                        (self._tc_height, self._tc_width, 3)
                    ).copy()
                    self.last_frame = frame
            except Exception as e:
                print(f"[DEBUG] ToupCam PullImageV4 gagal: {e}")
        elif nEvent in (sdk.TOUPCAM_EVENT_DISCONNECTED, sdk.TOUPCAM_EVENT_ERROR):
            print(f"[DEBUG] ToupCam event disconnect/error: {nEvent}")
            with self.lock:
                self._tc_connected = False
                self.last_frame = None

    def read(self):
        with self.lock:
            if self.backend == "toupcam":
                if not self._tc_connected or self._tc_handle is None:
                    return None
                return self.last_frame
            if self.cap is None or not self.cap.isOpened():
                return None
            ok, frame = self.cap.read()
            if not ok:
                self._opencv_read_failures += 1
                if self._opencv_read_failures >= OPENCV_DISCONNECT_THRESHOLD:
                    self._opencv_connected = False
                    self.last_frame = None
                return None
            self._opencv_read_failures = 0
            self._opencv_connected = True
            self.last_frame = frame
            return frame

    def capture(self):
        with self.lock:
            if self.last_frame is None:
                return None
            self.captured_frame = self.last_frame.copy()
            self.capture_seq += 1
            self.captured_focus_score = compute_focus_score(self.captured_frame)
            self.captured_quality = None
            self.captured_semantic = None
            return self.captured_frame

    def is_connected(self):
        if self.backend == "toupcam":
            return self._tc_handle is not None and self._tc_connected
        return self.cap is not None and self.cap.isOpened() and self._opencv_connected

    def open_settings_dialog(self):
        """Buka dialog properti bawaan driver DirectShow kamera (kalau didukung).

        Berguna buat atur exposure/white balance/dll manual langsung lewat
        kontrol bawaan drivernya sendiri. Cuma jalan di Windows + backend
        CAP_DSHOW; kamera lain (mis. webcam bawaan laptop) biasanya tidak
        butuh ini karena sudah nurut lewat cv2.set() biasa.
        """
        if os.name != "nt":
            return {"ok": False, "message": "Fitur ini hanya didukung di Windows (DirectShow)."}
        with self.lock:
            if self.cap is None or not self.cap.isOpened():
                return {"ok": False, "message": "Kamera belum terhubung."}
            try:
                self.cap.set(cv2.CAP_PROP_SETTINGS, 1)
            except Exception as e:
                return {"ok": False, "message": f"Gagal membuka dialog pengaturan: {e}"}
            actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return {"ok": True, "width": actual_w, "height": actual_h}


camera = CameraManager()


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


def gen_mjpeg():
    while True:
        frame = camera.read()
        if frame is None:
            time.sleep(0.2)
            continue
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
        )
        time.sleep(0.03)  # kurang lebih 30 fps


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


def generate_mock_instance_segmentation(frame):
    """PLACEHOLDER -- BUKAN model beneran.

    Rencananya di sini nanti dipasang inference Mask R-CNN/Detectron2 yang
    dilatih dari RBC Chula dataset. Buat sekarang, fungsi ini menghasilkan
    deteksi instance segmentation dummy (blob mirip lingkaran + kelas acak)
    supaya seluruh alur UI (overlay per kelas, daftar per-sel, koreksi
    manual, simpan hasil) bisa dibangun & dites end-to-end lebih dulu.

    Kontrak return-nya (list of dict dengan key classIndex/classLabel/
    confidence/bbox/mask) dipertahankan supaya nanti tinggal ganti ISI
    fungsi ini jadi manggil inference model beneran, tanpa perlu ubah kode
    di route atau di frontend.
    """
    h, w = frame.shape[:2]
    n_cells = random.randint(12, 24)
    detections = []

    # Bobot supaya "Normal cell" (index 0) lebih sering muncul, kira-kira
    # mirip proporsi asli di citra apusan darah (mayoritas sel normal).
    weights = [40] + [5] * (len(RBC_CLASS_LABELS) - 1)

    min_r = max(6, int(min(w, h) * 0.02))
    max_r = max(min_r + 4, int(min(w, h) * 0.045))

    for i in range(n_cells):
        cx = random.randint(max_r, max(max_r + 1, w - max_r))
        cy = random.randint(max_r, max(max_r + 1, h - max_r))
        r = random.randint(min_r, max_r)
        class_index = random.choices(range(len(RBC_CLASS_LABELS)), weights=weights, k=1)[0]
        confidence = round(random.uniform(0.55, 0.98), 3)

        # Bentuk mask sebagai polygon (bukan lingkaran sempurna, dikasih
        # noise dikit di radius) -- ini format yang sama dipakai instance
        # segmentation beneran (polygon per instance, gaya COCO).
        n_points = 16
        points = []
        for p in range(n_points):
            angle = 2 * math.pi * p / n_points
            rr = r * random.uniform(0.85, 1.1)
            points.append([
                round(cx + rr * math.cos(angle), 1),
                round(cy + rr * math.sin(angle), 1),
            ])

        bbox_x = max(0, cx - r)
        bbox_y = max(0, cy - r)
        detections.append({
            "id": i,
            "classIndex": class_index,
            "classLabel": RBC_CLASS_LABELS[class_index],
            "confidence": confidence,
            "bbox": [bbox_x, bbox_y, min(2 * r, w - bbox_x), min(2 * r, h - bbox_y)],
            "mask": points,
        })
    return detections


# ---------------------------------------------------------------------------
# Routes - segmentasi & klasifikasi morfologi sel
# ---------------------------------------------------------------------------
# Scaffold UI + hasil DUMMY dulu -- model instance segmentation beneran
# (rencana: Mask R-CNN/Detectron2, dilatih dari RBC Chula dataset) belum
# dilatih/dipasang. Kontrak response endpoint-endpoint ini sudah dirancang
# final (bukan sekadar placeholder acak) supaya begitu model beneran
# dipasang, frontend nggak perlu diubah lagi.
@app.route("/api/segmentation/classes")
def api_segmentation_classes():
    return jsonify([
        {"index": i, "label": label, "color": RBC_CLASS_COLORS[i]}
        for i, label in enumerate(RBC_CLASS_LABELS)
    ])


@app.route("/api/segmentation/select-image", methods=["POST"])
def api_segmentation_select_image():
    """Buka dialog pilih file gambar NATIVE lewat tkinter, baca isinya, dan
    kirim balik sebagai base64 buat preview (konsisten dengan pola
    /api/capture yang sudah ada -- bukan serve file lewat URL)."""
    result = {"path": None}

    def open_dialog():
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        result["path"] = filedialog.askopenfilename(
            title="Pilih Citra Apusan Darah",
            filetypes=[
                ("Gambar", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"),
                ("Semua file", "*.*"),
            ],
        )
        root.destroy()

    t = threading.Thread(target=open_dialog)
    t.start()
    t.join()

    if not result["path"]:
        return jsonify({"ok": False}), 400

    frame = cv2.imread(result["path"])
    if frame is None:
        return jsonify({"ok": False, "message": "Gagal membaca file gambar."}), 400

    b64 = frame_to_png_base64(frame)
    height, width = frame.shape[:2]
    return jsonify({
        "ok": True,
        "path": result["path"],
        "filename": os.path.basename(result["path"]),
        "image": b64,
        "width": width,
        "height": height,
    })


@app.route("/api/segmentation/run", methods=["POST"])
def api_segmentation_run():
    """PLACEHOLDER -- model instance segmentation beneran (Mask R-CNN/
    Detectron2, dilatih dari RBC Chula dataset) belum dilatih & dipasang.
    Endpoint ini mengembalikan deteksi DUMMY (lihat
    generate_mock_instance_segmentation) supaya seluruh alur UI bisa
    dibangun & dites duluan. Begitu modelnya siap, ganti isi fungsi ini jadi
    manggil inference beneran -- kontrak response-nya (detections +
    classCounts) dipertahankan supaya frontend nggak perlu diubah lagi."""
    data = request.json or {}
    path = (data.get("path") or "").strip()
    if not path or not os.path.isfile(path):
        return jsonify({"ok": False, "message": "Gambar sumber tidak valid."}), 400

    frame = cv2.imread(path)
    if frame is None:
        return jsonify({"ok": False, "message": "Gagal membaca gambar sumber."}), 400

    # Simulasi waktu proses model beneran, biar indikator progres di UI ada
    # gunanya buat dites -- kecilkan/hapus begitu inference asli dipasang.
    time.sleep(1.2)

    detections = generate_mock_instance_segmentation(frame)
    class_counts = {label: 0 for label in RBC_CLASS_LABELS}
    for d in detections:
        class_counts[d["classLabel"]] += 1

    height, width = frame.shape[:2]
    return jsonify({
        "ok": True,
        "mock": True,
        "message": (
            "Hasil DUMMY/Placeholder"
        ),
        "imageWidth": width,
        "imageHeight": height,
        "detections": detections,
        "classCounts": class_counts,
    })


def _load_segmentation_detail_file(detail_path):
    """Logic bersama buat baca satu file JSON hasil segmentasi + coba baca
    ulang gambar sumbernya buat preview. Dipakai baik dari dialog
    (/api/segmentation/load) maupun klik langsung di daftar hasil folder
    (/api/segmentation/load-path, tanpa buka dialog lagi -- ini yang bikin
    review banyak hasil sekaligus, mis. ~20 capture per pasien, nggak perlu
    buka-tutup dialog file satu-satu)."""
    try:
        with open(detail_path, "r", encoding="utf-8") as f:
            detail = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return {"ok": False, "message": f"Gagal membaca file: {e}"}

    source_image = detail.get("sourceImage")
    detections = detail.get("detections") or []

    response = {
        "ok": True,
        "path": source_image,
        "detailFile": os.path.basename(detail_path),
        "patientId": detail.get("patientId"),
        "detections": detections,
        "image": None,
        "width": None,
        "height": None,
    }

    if source_image and os.path.isfile(source_image):
        frame = cv2.imread(source_image)
        if frame is not None:
            response["image"] = frame_to_png_base64(frame)
            h, w = frame.shape[:2]
            response["width"] = w
            response["height"] = h

    if response["image"] is None:
        response["message"] = (
            "Gambar sumber asli tidak ditemukan/gagal dibaca di lokasi "
            "semula -- cuma daftar sel yang berhasil dimuat."
        )

    return response


@app.route("/api/segmentation/load", methods=["POST"])
def api_segmentation_load():
    """Buka file JSON hasil segmentasi yang sudah pernah disimpan lewat
    /api/segmentation/save, muat balik detections-nya (termasuk koreksi
    manual sebelumnya kalau ada), dan coba baca ulang gambar sumbernya buat
    preview -- biar user bisa lihat & lanjut koreksi tanpa mulai dari nol."""
    result = {"path": None}

    def open_dialog():
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        result["path"] = filedialog.askopenfilename(
            title="Pilih File Hasil Segmentasi (JSON)",
            filetypes=[("Hasil segmentasi (JSON)", "*.json"), ("Semua file", "*.*")],
        )
        root.destroy()

    t = threading.Thread(target=open_dialog)
    t.start()
    t.join()

    if not result["path"]:
        return jsonify({"ok": False}), 400

    return jsonify(_load_segmentation_detail_file(result["path"]))


@app.route("/api/segmentation/load-path", methods=["POST"])
def api_segmentation_load_path():
    """Sama seperti /api/segmentation/load, tapi path file JSON-nya dikirim
    langsung dari frontend (klik salah satu baris di daftar "Hasil di
    Folder Ini"), TANPA buka dialog file lagi -- dipakai buat review hasil
    batch (banyak gambar sekaligus, mis. satu pasien ~20 capture) tanpa
    perlu buka-tutup dialog satu-satu per gambar."""
    data = request.json or {}
    detail_path = (data.get("path") or "").strip()
    if not detail_path or not os.path.isfile(detail_path):
        return jsonify({"ok": False, "message": "File hasil tidak valid."}), 400
    return jsonify(_load_segmentation_detail_file(detail_path))


@app.route("/api/segmentation/list-results")
def api_segmentation_list_results():
    """Daftar hasil segmentasi TERBARU per gambar sumber di satu folder
    (dibaca dari segmentation_log.csv) -- ditampilkan sebagai daftar yang
    bisa diklik satu-satu di dalam aplikasi (lewat /load-path).

    Satu gambar bisa saja tercatat berkali-kali di log (mis. diproses
    individual dulu, terus ikut ke-proses lagi lewat batch, atau batch
    dijalankan dua kali) -- karena hasilnya masih DUMMY/acak, tiap proses
    ulang menghasilkan deteksi yang beda. Supaya nggak ambigu "yang mana
    yang berlaku", di sini CUMA baris dengan timestamp TERBARU per
    source_image yang ditampilkan; baris-baris lama tetap ada di CSV
    (nggak dihapus, buat jejak audit) tapi disembunyikan dari daftar ini."""
    folder = (request.args.get("folder") or "").strip()
    if not folder or not os.path.isdir(folder):
        return jsonify({"ok": False, "message": "Folder tidak valid."}), 400

    try:
        rows = _latest_segmentation_rows(folder)
    except OSError as e:
        return jsonify({"ok": False, "message": f"Gagal membaca log: {e}"}), 500

    results = [
        {
            "detailPath": os.path.join(folder, row.get("detail_file")),
            "detailFile": row.get("detail_file"),
            "sourceImage": row.get("source_image"),
            "patientId": row.get("patient_id"),
            "totalCells": row.get("total_cells"),
            "timestamp": row.get("timestamp"),
            "isDuplicate": (row.get("is_duplicate") or "0") == "1",
            "duplicateOfFile": row.get("duplicate_of") or None,
        }
        for row in rows
        if row.get("detail_file")
    ]
    results.sort(key=lambda r: r["timestamp"] or "", reverse=True)
    return jsonify({"ok": True, "folder": folder, "results": results})


@app.route("/api/segmentation/save", methods=["POST"])
def api_segmentation_save():
    """Simpan hasil segmentasi (termasuk koreksi manual dari UI, kalau ada)
    ke dua tempat, keduanya di folder yang sama dengan gambar sumbernya:
      1. File JSON detail per-sel (mask polygon, confidence, status koreksi)
      2. Satu baris ringkasan di segmentation_log.csv (jumlah sel per kelas
         -- format kolom per kelas biar gampang dianalisis langsung di Excel)

    Sebelum benar-benar nulis, dicek dulu apakah hasil ini PERSIS SAMA
    (total sel + jumlah per kelas identik) dengan hasil TERAKHIR yang sudah
    tersimpan buat gambar yang sama -- kalau iya dan client belum kirim
    `force: true`, nggak jadi ditulis, cuma balikin `needsConfirmation` biar
    frontend nanya dulu ke user (lihat doSaveSegmentation()). Ini buat
    nyegah folder numpuk banyak file JSON isinya sama persis tanpa sadar.
    """
    data = request.json or {}
    path = (data.get("path") or "").strip()
    patient_id = (data.get("patientId") or "").strip()
    detections = data.get("detections") or []
    force = bool(data.get("force"))

    if not path or not os.path.isfile(path):
        return jsonify({"ok": False, "message": "Gambar sumber tidak valid."}), 400
    if not detections:
        return jsonify({"ok": False, "message": "Belum ada hasil segmentasi untuk disimpan."}), 400

    folder = os.path.dirname(path)
    base_name = os.path.splitext(os.path.basename(path))[0]
    source_image_basename = os.path.basename(path)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    class_counts = {label: 0 for label in RBC_CLASS_LABELS}
    for d in detections:
        label = d.get("correctedClassLabel") or d.get("classLabel")
        if label in class_counts:
            class_counts[label] += 1

    # Agregasi penilaian dokter per sel (doctorVerdict: "correct"/"incorrect"/
    # null kalau belum direview) -- dipakai buat kolom ringkasan di
    # segmentation_log.csv & laporan Excel (lihat api_segmentation_export_report).
    doctor_correct_count = sum(1 for d in detections if d.get("doctorVerdict") == "correct")
    doctor_incorrect_count = sum(1 for d in detections if d.get("doctorVerdict") == "incorrect")
    doctor_reviewed_count = doctor_correct_count + doctor_incorrect_count

    with segmentation_log_lock:
        log_path = os.path.join(folder, SEGMENTATION_LOG_FILENAME)
        _ensure_log_columns(log_path, SEGMENTATION_LOG_FIELDNAMES)

        prev_row = next(
            (r for r in _latest_segmentation_rows(folder) if r.get("source_image") == source_image_basename),
            None,
        )
        is_duplicate = False
        duplicate_of = ""
        if prev_row is not None:
            try:
                prev_total = int(prev_row.get("total_cells") or 0)
                counts_match = all(
                    int(prev_row.get(label) or 0) == class_counts[label] for label in RBC_CLASS_LABELS
                )
                is_duplicate = counts_match and prev_total == len(detections)
            except (TypeError, ValueError):
                is_duplicate = False
            if is_duplicate:
                duplicate_of = prev_row.get("detail_file") or ""

        if is_duplicate and not force:
            return jsonify({
                "ok": True,
                "needsConfirmation": True,
                "isDuplicate": True,
                "lastTimestamp": prev_row.get("timestamp"),
                "lastDetailFile": duplicate_of,
            })

        detail_filename = f"{base_name}_segmentation_{timestamp}.json"
        detail_path = os.path.join(folder, detail_filename)
        # Timestamp cuma presisi per detik -- kalau ada dua save dalam detik
        # yang sama (mis. warning duplikat lalu langsung "tetap simpan"),
        # nama filenya bakal sama & nimpa file sebelumnya. Tambah suffix
        # numerik biar tetap unik.
        dedup_suffix = 1
        while os.path.exists(detail_path):
            detail_filename = f"{base_name}_segmentation_{timestamp}-{dedup_suffix}.json"
            detail_path = os.path.join(folder, detail_filename)
            dedup_suffix += 1
        try:
            with open(detail_path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": timestamp,
                    "patientId": patient_id,
                    "sourceImage": path,
                    "detections": detections,
                    "isDuplicate": is_duplicate,
                    "duplicateOfFile": duplicate_of or None,
                }, f, ensure_ascii=False, indent=2)
        except OSError as e:
            return jsonify({"ok": False, "message": f"Gagal menyimpan file detail: {e}"}), 500

        is_new = not os.path.exists(log_path)
        row = {
            "timestamp": timestamp,
            "patient_id": patient_id or "?",
            "source_image": source_image_basename,
            "detail_file": detail_filename,
            "total_cells": len(detections),
            "is_duplicate": "1" if is_duplicate else "0",
            "duplicate_of": duplicate_of,
            "doctor_reviewed_count": doctor_reviewed_count,
            "doctor_correct_count": doctor_correct_count,
            "doctor_incorrect_count": doctor_incorrect_count,
            **class_counts,
        }
        try:
            with open(log_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=SEGMENTATION_LOG_FIELDNAMES)
                if is_new:
                    writer.writeheader()
                writer.writerow(row)
        except OSError as e:
            return jsonify({"ok": False, "message": f"Gagal menulis log: {e}"}), 500

    return jsonify({
        "ok": True,
        "detailPath": detail_path,
        "logPath": log_path,
        "totalCells": len(detections),
        "isDuplicate": is_duplicate,
    })


@app.route("/api/segmentation/batch-select", methods=["POST"])
def api_segmentation_batch_select():
    """Dialog pilih FOLDER buat proses batch -- daftar file gambar langsung
    di dalam folder itu (bukan rekursif ke subfolder) dikembalikan supaya
    frontend bisa konfirmasi dulu jumlahnya ke user sebelum benar-benar
    diproses (bisa makan waktu kalau isinya banyak)."""
    result = {"path": None}

    def open_dialog():
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        result["path"] = filedialog.askdirectory(title="Pilih Folder Citra untuk Diproses Batch")
        root.destroy()

    t = threading.Thread(target=open_dialog)
    t.start()
    t.join()

    if not result["path"]:
        return jsonify({"ok": False}), 400

    image_exts = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")
    try:
        files = sorted(
            f for f in os.listdir(result["path"])
            if f.lower().endswith(image_exts) and os.path.isfile(os.path.join(result["path"], f))
        )
    except OSError as e:
        return jsonify({"ok": False, "message": f"Gagal membaca isi folder: {e}"}), 400

    return jsonify({"ok": True, "folder": result["path"], "files": files})


@app.route("/api/segmentation/batch-run", methods=["POST"])
def api_segmentation_batch_run():
    """PLACEHOLDER -- proses SEMUA gambar dalam satu folder sekaligus:
    jalankan (mock) instance segmentation + langsung simpan hasilnya (JSON
    detail + baris di segmentation_log.csv) untuk tiap gambar, tanpa jeda
    buat koreksi manual per gambar (koreksi tetap bisa dilakukan belakangan
    per file lewat "Muat Hasil Tersimpan"). Model instance segmentation
    beneran belum dilatih -- begitu siap, ganti pemanggilan
    generate_mock_instance_segmentation() di bawah jadi inference asli,
    sisanya (penyimpanan, agregasi) nggak perlu diubah."""
    data = request.json or {}
    folder = (data.get("folder") or "").strip()
    patient_id = (data.get("patientId") or "").strip()
    skip_existing = bool(data.get("skipExisting"))
    if not folder or not os.path.isdir(folder):
        return jsonify({"ok": False, "message": "Folder tidak valid."}), 400

    image_exts = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")
    files = sorted(
        f for f in os.listdir(folder)
        if f.lower().endswith(image_exts) and os.path.isfile(os.path.join(folder, f))
    )
    if not files:
        return jsonify({"ok": False, "message": "Tidak ada file gambar di folder ini."}), 400

    grand_total_counts = {label: 0 for label in RBC_CLASS_LABELS}
    per_image_results = []
    already_processed = set()

    with segmentation_log_lock:
        log_path = os.path.join(folder, SEGMENTATION_LOG_FILENAME)
        _ensure_log_columns(log_path, SEGMENTATION_LOG_FIELDNAMES)
        is_new_log = not os.path.exists(log_path)

        if skip_existing and os.path.isfile(log_path):
            try:
                with open(log_path, "r", newline="", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        si = row.get("source_image")
                        if si:
                            already_processed.add(si)
            except OSError:
                pass

        for fname in files:
            if skip_existing and fname in already_processed:
                per_image_results.append({
                    "filename": fname, "ok": True, "skipped": True,
                    "message": "Dilewati -- sudah pernah diproses sebelumnya.",
                })
                continue

            fpath = os.path.join(folder, fname)
            frame = cv2.imread(fpath)
            if frame is None:
                per_image_results.append({"filename": fname, "ok": False, "message": "Gagal dibaca."})
                continue

            # Delay simulasi diperkecil dibanding mode satu-gambar, biar
            # batch banyak file nggak kelamaan -- hapus kalau model beneran
            # sudah dipasang (delay ini murni buat placeholder).
            time.sleep(0.3)
            detections = generate_mock_instance_segmentation(frame)

            base_name = os.path.splitext(fname)[0]
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            detail_filename = f"{base_name}_segmentation_{timestamp}.json"
            detail_path = os.path.join(folder, detail_filename)
            try:
                with open(detail_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "timestamp": timestamp,
                        "patientId": patient_id,
                        "sourceImage": fpath,
                        "detections": detections,
                    }, f, ensure_ascii=False, indent=2)
            except OSError as e:
                per_image_results.append({"filename": fname, "ok": False, "message": f"Gagal menyimpan detail: {e}"})
                continue

            class_counts = {label: 0 for label in RBC_CLASS_LABELS}
            for d in detections:
                class_counts[d["classLabel"]] += 1
                grand_total_counts[d["classLabel"]] += 1

            row = {
                "timestamp": timestamp,
                "patient_id": patient_id or "?",
                "source_image": fname,
                "detail_file": detail_filename,
                "total_cells": len(detections),
                "is_duplicate": "0",  # batch selalu jalankan segmentasi baru, nggak dicek duplikat
                "duplicate_of": "",
                # Hasil batch murni mock otomatis, belum pernah direview dokter
                # satu-satu -- kolomnya tetap diisi 0 biar CSV konsisten.
                "doctor_reviewed_count": 0,
                "doctor_correct_count": 0,
                "doctor_incorrect_count": 0,
                **class_counts,
            }
            try:
                with open(log_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=SEGMENTATION_LOG_FIELDNAMES)
                    if is_new_log:
                        writer.writeheader()
                        is_new_log = False
                    writer.writerow(row)
            except OSError as e:
                per_image_results.append({"filename": fname, "ok": False, "message": f"Gagal menulis log: {e}"})
                continue

            per_image_results.append({
                "filename": fname,
                "ok": True,
                "totalCells": len(detections),
                "classCounts": class_counts,
                "detailFile": detail_filename,
            })

    total_skipped = sum(1 for r in per_image_results if r.get("skipped"))
    total_processed = sum(1 for r in per_image_results if r["ok"] and not r.get("skipped"))
    return jsonify({
        "ok": True,
        "mock": True,
        "folder": folder,
        "totalImages": len(files),
        "totalImagesOk": sum(1 for r in per_image_results if r["ok"]),
        "totalSkipped": total_skipped,
        "grandTotalCounts": grand_total_counts,
        "perImage": per_image_results,
        "message": (
            f"Batch selesai (hasil DUMMY/placeholder) -- {total_processed} gambar diproses"
            + (f", {total_skipped} dilewati (sudah ada)" if total_skipped else "")
            + ". Model instance segmentation beneran belum dilatih."
        ),
    })


@app.route("/api/segmentation/check-existing")
def api_segmentation_check_existing():
    """Cek apakah satu gambar (by path) sudah pernah punya hasil segmentasi
    tersimpan di segmentation_log.csv folder yang sama -- dipakai buat
    warning sebelum reprocess individual (biar nggak nggak sadar bikin
    hasil baru yang beda random dari yang lama, lihat juga skipExisting di
    /batch-run buat kasus batch)."""
    path = (request.args.get("path") or "").strip()
    if not path:
        return jsonify({"exists": False})

    folder = os.path.dirname(path)
    fname = os.path.basename(path)
    log_path = os.path.join(folder, SEGMENTATION_LOG_FILENAME)
    if not os.path.isfile(log_path):
        return jsonify({"exists": False})

    latest = None
    try:
        with open(log_path, "r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("source_image") != fname:
                    continue
                ts = row.get("timestamp") or ""
                if latest is None or ts >= (latest.get("timestamp") or ""):
                    latest = row
    except OSError:
        return jsonify({"exists": False})

    if latest is None:
        return jsonify({"exists": False})

    return jsonify({
        "exists": True,
        "detailFile": latest.get("detail_file"),
        "totalCells": latest.get("total_cells"),
        "timestamp": latest.get("timestamp"),
    })


@app.route("/api/segmentation/patient-summary")
def api_segmentation_patient_summary():
    """Agregasi segmentation_log.csv per patient_id dalam satu folder --
    total gambar, total sel, dan breakdown per kelas.

    Dedup dulu per source_image (ambil baris TERBARU aja per gambar,
    sama seperti /api/segmentation/list-results) SEBELUM diagregasi --
    kalau tidak, gambar yang kebetulan diproses lebih dari sekali
    (individual lalu ikut batch, atau batch dijalankan dua kali) bakal
    kehitung dobel/lebih di total & breakdown per kelas."""
    folder = (request.args.get("folder") or "").strip()
    if not folder or not os.path.isdir(folder):
        return jsonify({"ok": False, "message": "Folder tidak valid."}), 400

    try:
        rows = _latest_segmentation_rows(folder)
    except OSError as e:
        return jsonify({"ok": False, "message": f"Gagal membaca log: {e}"}), 500

    patients = {}
    for row in rows:
        pid = row.get("patient_id") or "?"
        if pid not in patients:
            patients[pid] = {
                "patientId": pid,
                "totalImages": 0,
                "totalCells": 0,
                "totalReviewed": 0,
                "totalCorrect": 0,
                "totalIncorrect": 0,
                "classCounts": {label: 0 for label in RBC_CLASS_LABELS},
            }
        patients[pid]["totalImages"] += 1
        try:
            patients[pid]["totalCells"] += int(row.get("total_cells") or 0)
        except ValueError:
            pass
        for key, field in (
            ("totalReviewed", "doctor_reviewed_count"),
            ("totalCorrect", "doctor_correct_count"),
            ("totalIncorrect", "doctor_incorrect_count"),
        ):
            try:
                patients[pid][key] += int(row.get(field) or 0)
            except (ValueError, TypeError):
                pass
        for label in RBC_CLASS_LABELS:
            try:
                patients[pid]["classCounts"][label] += int(row.get(label) or 0)
            except (ValueError, TypeError):
                pass

    return jsonify({
        "ok": True,
        "patients": sorted(patients.values(), key=lambda p: p["patientId"]),
    })


@app.route("/api/segmentation/model-status")
def api_segmentation_model_status():
    config = _load_model_config()
    model_path = (config.get("modelPath") or "").strip()
    model_file_found = bool(model_path) and os.path.isfile(model_path)
    if model_path:
        detail = (
            f'Path model tersimpan ("{model_path}"), tapi kode inference asli belum '
            "dipasang -- ini baru tempat konfigurasi buat nanti."
        )
    else:
        detail = "Belum ada path model dikonfigurasi."
    return jsonify({
        "ok": True,
        "usingMock": True,
        "modelPath": model_path,
        "modelFileFound": model_file_found,
        "lowConfidenceThreshold": config["lowConfidenceThreshold"],
        "message": "Semua hasil segmentasi saat ini masih DUMMY/placeholder. " + detail,
    })


@app.route("/api/segmentation/model-config", methods=["POST"])
def api_segmentation_model_config():
    data = request.json or {}
    model_path = (data.get("modelPath") or "").strip()
    try:
        threshold = int(data.get("lowConfidenceThreshold"))
        if not (1 <= threshold <= 100):
            raise ValueError
    except (TypeError, ValueError):
        threshold = DEFAULT_LOW_CONFIDENCE_THRESHOLD
    try:
        with open(MODEL_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {"modelPath": model_path, "lowConfidenceThreshold": threshold},
                f, ensure_ascii=False, indent=2,
            )
    except OSError as e:
        return jsonify({"ok": False, "message": f"Gagal menyimpan konfigurasi: {e}"}), 500
    return jsonify({"ok": True, "modelPath": model_path, "lowConfidenceThreshold": threshold})


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
