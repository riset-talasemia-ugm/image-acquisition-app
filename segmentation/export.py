"""Export hasil segmentasi: laporan Excel dan dataset COCO."""

import json
import os
from datetime import datetime

import cv2
from flask import jsonify, request

from config import RBC_CLASS_LABELS
from segmentation import segmentation_bp
from segmentation.storage import _latest_segmentation_rows, _load_model_config, active_detections
from utils import safe_slug


@segmentation_bp.route("/api/segmentation/export-report", methods=["POST"])
def api_segmentation_export_report():
    """Export laporan ringkasan hasil segmentasi satu folder ke file Excel
    (2 sheet: ringkasan per pasien, dan detail per gambar) -- dedup terbaru
    per gambar, konsisten sama yang ditampilkan di aplikasi (Ringkasan per
    Pasien / Hasil di Folder Ini). Kalau patientId diisi, cuma pasien itu
    yang diekspor; kalau kosong, semua pasien di folder itu."""
    data = request.json or {}
    folder = (data.get("folder") or "").strip()
    patient_id_filter = (data.get("patientId") or "").strip()
    if not folder or not os.path.isdir(folder):
        return jsonify({"ok": False, "message": "Folder tidak valid."}), 400

    rows = _latest_segmentation_rows(folder)
    if patient_id_filter:
        rows = [r for r in rows if (r.get("patient_id") or "") == patient_id_filter]
    if not rows:
        return jsonify({"ok": False, "message": "Tidak ada hasil yang cocok untuk diekspor."}), 400

    try:
        import openpyxl
        from openpyxl.styles import Font
    except ImportError:
        return jsonify({
            "ok": False,
            "message": "Library openpyxl belum terinstall di server (pip install openpyxl).",
        }), 500

    wb = openpyxl.Workbook()

    doctor_cols = ["Direview Dokter", "Benar (Dokter)", "Salah (Dokter)"]

    ws1 = wb.active
    ws1.title = "Ringkasan Pasien"
    ws1.append(["ID Pasien", "Jumlah Gambar", "Total Sel"] + doctor_cols + RBC_CLASS_LABELS)
    for cell in ws1[1]:
        cell.font = Font(bold=True)

    patients = {}
    for row in rows:
        pid = row.get("patient_id") or "?"
        if pid not in patients:
            patients[pid] = {
                "images": 0,
                "totalCells": 0,
                "reviewed": 0,
                "correct": 0,
                "incorrect": 0,
                "counts": {l: 0 for l in RBC_CLASS_LABELS},
            }
        patients[pid]["images"] += 1
        try:
            patients[pid]["totalCells"] += int(row.get("total_cells") or 0)
        except ValueError:
            pass
        for key in ("reviewed", "correct", "incorrect"):
            try:
                patients[pid][key] += int(row.get(f"doctor_{key}_count") or 0)
            except (ValueError, TypeError):
                pass
        for label in RBC_CLASS_LABELS:
            try:
                patients[pid]["counts"][label] += int(row.get(label) or 0)
            except (ValueError, TypeError):
                pass
    for pid, agg in sorted(patients.items()):
        ws1.append(
            [pid, agg["images"], agg["totalCells"], agg["reviewed"], agg["correct"], agg["incorrect"]]
            + [agg["counts"][l] for l in RBC_CLASS_LABELS]
        )

    ws2 = wb.create_sheet("Detail per Gambar")
    ws2.append(["Timestamp", "ID Pasien", "Gambar", "Total Sel"] + doctor_cols + RBC_CLASS_LABELS)
    for cell in ws2[1]:
        cell.font = Font(bold=True)
    for row in sorted(rows, key=lambda r: r.get("timestamp") or ""):
        ws2.append(
            [row.get("timestamp"), row.get("patient_id"), row.get("source_image"), row.get("total_cells")]
            + [row.get("doctor_reviewed_count"), row.get("doctor_correct_count"), row.get("doctor_incorrect_count")]
            + [row.get(l) for l in RBC_CLASS_LABELS]
        )

    # Sheet ketiga: satu baris per SEL terdeteksi (bukan per gambar/pasien) --
    # butuh baca ulang tiap file JSON detail (segmentation_log.csv cuma nyimpen
    # ringkasan per gambar, bukan per sel). File yang hilang/rusak dilewati
    # (baris itu aja) supaya satu file bermasalah nggak menggagalkan seluruh
    # export.
    ws3 = wb.create_sheet("Detail per Sel")
    ws3.append([
        "Timestamp", "ID Pasien", "Gambar", "No. Sel", "Kelas Model",
        "Kelas Dikoreksi", "Confidence (%)", "Manual", "Verdict Dokter",
    ])
    for cell in ws3[1]:
        cell.font = Font(bold=True)
    for row in sorted(rows, key=lambda r: r.get("timestamp") or ""):
        detail_file = row.get("detail_file")
        if not detail_file:
            continue
        detail_path = os.path.join(folder, detail_file)
        try:
            with open(detail_path, "r", encoding="utf-8") as f:
                detail = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        for i, d in enumerate(active_detections(detail.get("detections"))):
            corrected_idx = d.get("correctedClassIndex")
            has_correction = corrected_idx is not None and corrected_idx != d.get("classIndex")
            verdict = {"correct": "Benar", "incorrect": "Salah"}.get(d.get("doctorVerdict"), "-")
            confidence = d.get("confidence")
            ws3.append([
                row.get("timestamp"),
                row.get("patient_id"),
                row.get("source_image"),
                i + 1,
                d.get("classLabel"),
                d.get("correctedClassLabel") if has_correction else "",
                round(confidence * 100, 1) if isinstance(confidence, (int, float)) else confidence,
                "Ya" if d.get("manual") else "Tidak",
                verdict,
            ])

    for ws in (ws1, ws2, ws3):
        for col_cells in ws.columns:
            length = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells)
            ws.column_dimensions[col_cells[0].column_letter].width = min(30, max(10, length + 2))

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_patient = safe_slug(patient_id_filter) if patient_id_filter else "semua-pasien"
    # Timestamp cuma presisi per detik -- dua export cepat berturut-turut bisa
    # jatuh di detik yang sama dan nimpa file satu sama lain tanpa peringatan
    # kalau nama filenya sama persis (bug yang sama ditemukan & diperbaiki di
    # api_segmentation_export_coco). Tambah suffix numerik biar tetap unik.
    dedup_suffix = 0
    filename = f"laporan_segmentasi_{safe_patient}_{timestamp}.xlsx"
    export_path = os.path.join(folder, filename)
    while os.path.exists(export_path):
        dedup_suffix += 1
        filename = f"laporan_segmentasi_{safe_patient}_{timestamp}-{dedup_suffix}.xlsx"
        export_path = os.path.join(folder, filename)
    try:
        wb.save(export_path)
    except OSError as e:
        return jsonify({"ok": False, "message": f"Gagal menyimpan file laporan: {e}"}), 500

    return jsonify({"ok": True, "path": export_path, "filename": filename})


def _polygon_area(points):
    """Luas polygon sederhana (shoelace formula) -- dipakai buat field "area"
    di annotation COCO, nggak butuh dependency tambahan apapun."""
    n = len(points)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


@segmentation_bp.route("/api/segmentation/export-coco", methods=["POST"])
def api_segmentation_export_coco():
    """Export hasil segmentasi satu folder ke satu file annotations.json
    format COCO instance segmentation (images/annotations/categories) --
    siap dipakai buat training Mask R-CNN/Detectron2 nanti begitu model
    aslinya mulai dikerjakan. Beda dari export-report (Excel, buat dibaca
    manusia), ini format standar yang langsung bisa dimuat library training.

    Kelas yang dipakai per sel selalu kelas EFEKTIF-nya (correctedClassLabel
    kalau ada koreksi, kalau tidak classLabel asli model) -- sama seperti
    logic class_counts di api_segmentation_save.

    onlyReviewed=True: cuma sel dengan doctorVerdict terisi yang masuk. Sel
    "incorrect" TANPA correctedClassIndex (dokter cuma tandai salah, belum
    sempat ganti kelasnya) sengaja DILEWATI biar nggak nyemarin dataset
    dengan label yang sudah diketahui keliru -- bukan disertakan pakai label
    asli yang salah itu."""
    data = request.json or {}
    folder = (data.get("folder") or "").strip()
    patient_id_filter = (data.get("patientId") or "").strip()
    only_reviewed = bool(data.get("onlyReviewed"))
    if not folder or not os.path.isdir(folder):
        return jsonify({"ok": False, "message": "Folder tidak valid."}), 400

    rows = _latest_segmentation_rows(folder)
    if patient_id_filter:
        rows = [r for r in rows if (r.get("patient_id") or "") == patient_id_filter]
    if not rows:
        return jsonify({"ok": False, "message": "Tidak ada hasil yang cocok untuk diekspor."}), 400

    category_by_label = {label: i + 1 for i, label in enumerate(RBC_CLASS_LABELS)}
    categories = [{"id": i + 1, "name": label} for i, label in enumerate(RBC_CLASS_LABELS)]

    images = []
    annotations = []
    skipped_images = 0
    skipped_cells = 0
    next_image_id = 1
    next_ann_id = 1

    for row in sorted(rows, key=lambda r: r.get("timestamp") or ""):
        detail_file = row.get("detail_file")
        if not detail_file:
            continue
        detail_path = os.path.join(folder, detail_file)
        try:
            with open(detail_path, "r", encoding="utf-8") as f:
                detail = json.load(f)
        except (OSError, json.JSONDecodeError):
            skipped_images += 1
            continue

        source_image = detail.get("sourceImage")
        frame = cv2.imread(source_image) if source_image else None
        if frame is None:
            skipped_images += 1
            continue
        height, width = frame.shape[:2]

        image_id = next_image_id
        next_image_id += 1
        images.append({
            "id": image_id,
            "file_name": os.path.basename(source_image),
            "width": width,
            "height": height,
        })

        for d in active_detections(detail.get("detections")):
            corrected_idx = d.get("correctedClassIndex")
            has_correction = corrected_idx is not None and corrected_idx != d.get("classIndex")
            label = d.get("correctedClassLabel") if has_correction else d.get("classLabel")
            verdict = d.get("doctorVerdict")

            if only_reviewed:
                if verdict not in ("correct", "incorrect"):
                    skipped_cells += 1
                    continue
                if verdict == "incorrect" and not has_correction:
                    skipped_cells += 1
                    continue

            category_id = category_by_label.get(label)
            mask = d.get("mask") or []
            if category_id is None or len(mask) < 3:
                skipped_cells += 1
                continue

            bbox = d.get("bbox")
            if not bbox or len(bbox) != 4:
                xs = [p[0] for p in mask]
                ys = [p[1] for p in mask]
                bbox = [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]

            annotations.append({
                "id": next_ann_id,
                "image_id": image_id,
                "category_id": category_id,
                "segmentation": [[coord for point in mask for coord in point]],
                "area": _polygon_area(mask),
                "bbox": bbox,
                "iscrowd": 0,
            })
            next_ann_id += 1

    if not images:
        return jsonify({"ok": False, "message": "Tidak ada gambar yang berhasil dibaca untuk diekspor."}), 400

    model_path = (_load_model_config().get("modelPath") or "").strip()
    coco = {
        "info": {
            "description": (
                "Dataset diekspor dari Thalassemia Capture App. "
                + (
                    f'Dihasilkan model mock (belum ada inference asli; modelPath tersimpan: "{model_path}").'
                    if not model_path
                    else f'modelPath tersimpan: "{model_path}" -- cek apakah inference asli sudah terpasang.'
                )
            ),
            "date_created": datetime.now().isoformat(),
        },
        "images": images,
        "annotations": annotations,
        "categories": categories,
    }

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_patient = safe_slug(patient_id_filter) if patient_id_filter else "semua-pasien"
    # Timestamp cuma presisi per detik -- dua export cepat berturut-turut
    # (mis. toggle checkbox lalu export lagi) bisa jatuh di detik yang sama
    # dan nimpa file satu sama lain tanpa peringatan kalau nama filenya sama
    # persis. Tambah suffix numerik biar tetap unik (pola sama seperti
    # detail_filename di api_segmentation_save).
    dedup_suffix = 0
    filename = f"dataset_coco_{safe_patient}_{timestamp}.json"
    export_path = os.path.join(folder, filename)
    while os.path.exists(export_path):
        dedup_suffix += 1
        filename = f"dataset_coco_{safe_patient}_{timestamp}-{dedup_suffix}.json"
        export_path = os.path.join(folder, filename)
    try:
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(coco, f, ensure_ascii=False, indent=2)
    except OSError as e:
        return jsonify({"ok": False, "message": f"Gagal menyimpan dataset: {e}"}), 500

    skip_note = ""
    if skipped_images or skipped_cells:
        skip_note = (
            f" ({skipped_images} gambar dilewati (tidak terbaca), "
            f"{skipped_cells} sel dilewati (belum direview/koreksi tidak lengkap))"
        )
    return jsonify({
        "ok": True,
        "path": export_path,
        "filename": filename,
        "message": f"Dataset COCO tersimpan: {len(images)} gambar, {len(annotations)} sel{skip_note}.",
    })
