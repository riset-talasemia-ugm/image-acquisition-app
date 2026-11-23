"""Blueprint report_bp: laporan pasien siap cetak (UC-07, docs/use-case.md bagian 5).

Halaman HTML A4; PDF dibuat lewat Cetak > Simpan sebagai PDF di browser, jadi
tidak butuh dependency baru dan jalan offline. Angka diambil dari hasil
segmentasi terbaru per citra (kelas akhir sesudah koreksi dokter) dan dari
capture_log.csv. Nama file dan path sengaja tidak ditampilkan.
"""

import base64
import csv
import json
import os
from datetime import datetime

import cv2
import numpy as np
from flask import Blueprint, render_template, request

from config import APP_VERSION, LOG_FILENAME, RBC_CLASS_LABELS, SCREENING_MIN_RBC
from segmentation.storage import _latest_segmentation_rows, _load_model_config, active_detections
from utils import safe_slug

report_bp = Blueprint("report", __name__)


def _thumb_b64(path, width=360):
    frame = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR) if os.path.isfile(path) else None
    if frame is None:
        return None
    h, w = frame.shape[:2]
    frame = cv2.resize(frame, (width, max(1, round(h * width / w))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode("ascii") if ok else None


def patient_report(folder, patient):
    """Kumpulkan angka laporan satu pasien di satu folder."""
    slug = safe_slug(patient)
    rows = [r for r in _latest_segmentation_rows(folder) if safe_slug(r.get("patient_id") or "") == slug]
    counts = {label: 0 for label in RBC_CLASS_LABELS}
    total = reviewed = corrected = added = 0
    images = []
    for row in sorted(rows, key=lambda r: r.get("source_image") or ""):
        try:
            with open(os.path.join(folder, row.get("detail_file") or ""), encoding="utf-8") as f:
                detections = active_detections(json.load(f).get("detections"))
        except (OSError, ValueError):
            continue
        images.append(row.get("source_image"))
        for d in detections:
            label = d.get("correctedClassLabel") or d.get("classLabel")
            if label in counts:
                counts[label] += 1
            total += 1
            reviewed += 1 if d.get("doctorVerdict") else 0
            idx = d.get("correctedClassIndex")
            corrected += 1 if idx is not None and idx != d.get("classIndex") else 0
            added += 1 if d.get("manual") else 0

    quality = {"baik": 0, "sedang": 0, "buram": 0, "lain": 0}
    log_path = os.path.join(folder, LOG_FILENAME)
    if os.path.isfile(log_path):
        with open(log_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("filename") in images:
                    status = row.get("focus_status") or ""
                    quality[status if status in quality else "lain"] += 1

    rbc = total - counts.get("Uncategorised", 0)
    classes = [
        {"label": label, "n": n, "pct": (100.0 * n / total) if total else 0.0}
        for label, n in counts.items()
    ]
    examples = [b for b in (_thumb_b64(os.path.join(folder, name)) for name in images[:4]) if b]
    return {
        "patient": patient,
        "images": len(images),
        "total": total,
        "rbc": rbc,
        "rbcTarget": SCREENING_MIN_RBC,
        "reviewed": reviewed,
        "corrected": corrected,
        "added": added,
        "classes": classes,
        "quality": quality,
        "examples": examples,
    }


@report_bp.route("/laporan")
def laporan():
    folder = (request.args.get("folder") or "").strip()
    patient = (request.args.get("patient") or "").strip()
    if not folder or not os.path.isdir(folder) or not patient:
        return "Folder atau inisial pasien belum valid. Tutup halaman ini, lalu buka lagi dari Analisis sel.", 400
    data = patient_report(folder, patient)
    now = datetime.now()
    config = _load_model_config()
    return render_template(
        "laporan.html",
        r=data,
        date=now.strftime("%d-%m-%Y"),
        number=f"{safe_slug(patient).upper()}-{now.strftime('%Y%m%d')}",
        version=APP_VERSION,
        model_mock=True,  # model asli belum terpasang (lihat /api/segmentation/model-status)
        model_path=config.get("modelPath") or "",
    )
