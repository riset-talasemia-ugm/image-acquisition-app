"""Baca hasil segmentasi tersimpan (segmentation_log.csv, JSON detail) dan konfigurasi model."""

import csv
import json
import os

import cv2

from config import DEFAULT_LOW_CONFIDENCE_THRESHOLD, MODEL_CONFIG_PATH, SEGMENTATION_LOG_FILENAME
from utils import frame_to_png_base64


def _latest_segmentation_rows(folder):
    """Baca segmentation_log.csv di satu folder, dedup ambil baris TERBARU
    per source_image -- helper yang sama dipakai /list-results dan
    /patient-summary, dipusatkan di sini juga buat /export-report.

    Kalau dua baris punya timestamp yang PERSIS sama (resolusi timestamp
    cuma per detik, bisa kejadian kalau ada save cepat berturut-turut,
    mis. warning duplikat lalu "tetap simpan"), baris yang lebih BELAKANGAN
    di file (ditulis lebih baru) yang menang -- makanya perbandingannya
    `>` bukan `>=`, biar baris lama nggak "menang" cuma gara-gara duluan
    ditulis di file."""
    log_path = os.path.join(folder, SEGMENTATION_LOG_FILENAME)
    if not os.path.isfile(log_path):
        return []
    latest_by_image = {}
    with open(log_path, "r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            si = row.get("source_image")
            if not si:
                continue
            ts = row.get("timestamp") or ""
            existing = latest_by_image.get(si)
            if existing is not None and existing.get("timestamp", "") > ts:
                continue
            latest_by_image[si] = row
    return list(latest_by_image.values())


# ---------------------------------------------------------------------------
# Status & konfigurasi model segmentasi
# ---------------------------------------------------------------------------


def _load_model_config():
    config = {"modelPath": "", "lowConfidenceThreshold": DEFAULT_LOW_CONFIDENCE_THRESHOLD}
    if os.path.isfile(MODEL_CONFIG_PATH):
        try:
            with open(MODEL_CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                config.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass
    try:
        threshold = int(config.get("lowConfidenceThreshold"))
        if not (1 <= threshold <= 100):
            raise ValueError
        config["lowConfidenceThreshold"] = threshold
    except (TypeError, ValueError):
        config["lowConfidenceThreshold"] = DEFAULT_LOW_CONFIDENCE_THRESHOLD
    return config


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
        **({"labelMode": detail["labelMode"]} if detail.get("labelMode") else {}),  # tanpa field = satu kelas
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
