"""Baca hasil segmentasi tersimpan (segmentation_log.csv, JSON detail) dan konfigurasi model."""

import csv
import json
import os

from config import DEFAULT_LOW_CONFIDENCE_THRESHOLD, MODEL_CONFIG_PATH, SEGMENTATION_LOG_FILENAME


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
