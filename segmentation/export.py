"""Export hasil segmentasi: laporan Excel dan dataset COCO."""

import json
import os
from datetime import datetime

import cv2
from flask import jsonify, request

from attributes import BENTUK
from config import RBC_CLASS_LABELS
from segmentation import segmentation_bp
from segmentation.compare import (
    DELETED, agreement_pairs, attribute_stats, cell_attributes, cohen_kappa, comparison_cells,
    corrected_parts, fmt_attrs, load_details, pct, rbc_count,
)
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

    _add_attribute_sheets(wb, Font, load_details(folder, rows))

    for ws in wb.worksheets:
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


def _add_attribute_sheets(wb, Font, details):
    """Sheet tambahan sesudah v0.1.0: proporsi atribut per pasien dan koreksi dokter per sel.
    Sheet v0.1.0 (Ringkasan Pasien, Detail per Gambar, Detail per Sel) tidak berubah."""
    ws = wb.create_sheet("Atribut per Pasien")
    ws.append(["ID Pasien", "Sel beratribut", "% mikrosit", "% normosit", "% makrosit", "% ukuran tidak diketahui",
               "% hipokrom"] + [f"% {b}" for b in BENTUK] + ["Sumber atribut"])
    per_patient = {}
    for row, detail in details:
        mode = detail.get("labelMode", "single")
        for d in detail.get("detections") or []:
            if d.get("deletedByDoctor"):
                continue
            attrs, source = cell_attributes(d, mode)
            entry = per_patient.setdefault(row.get("patient_id") or "?", {"attrs": [], "sources": {}})
            entry["attrs"].append(attrs)
            if source:
                entry["sources"][source] = entry["sources"].get(source, 0) + 1
    any_attr = False
    for pid, entry in sorted(per_patient.items()):
        st = attribute_stats(entry["attrs"])
        if not st["n"]:
            continue
        any_attr = True
        u = st["ukuran"]
        ws.append([pid, st["n"]] + [pct(u.get(k, 0), st["n"]) for k in ("mikrosit", "normosit", "makrosit", "tidak diketahui")]
                  + [pct(st["hipokrom"], st["n"])] + [pct(st["bentuk"][b], st["n"]) for b in BENTUK]
                  + ["; ".join(f"{k} {v}" for k, v in sorted(entry["sources"].items()))])
    if not any_attr:
        ws.append(["Belum ada hasil dari model atribut (ukuran, bentuk, warna)."])

    ws2 = wb.create_sheet("Koreksi per Sel")
    ws2.append(["ID Pasien", "Gambar", "No. Sel", "Kelas sistem", "Kelas dokter", "Dikoreksi dokter",
                "Verdict dokter", "Model: ukuran", "Model: bentuk", "Model: warna",
                "Akhir: ukuran", "Akhir: bentuk", "Akhir: warna", "Sumber atribut"])
    for row, detail in details:
        mode = detail.get("labelMode", "single")
        for no, d, system, doctor in comparison_cells(detail):
            attrs, source = cell_attributes(d, mode)
            parts = ("dihapus" if d.get("deletedByDoctor") else "ditambah" if d.get("manual")
                     else ", ".join(corrected_parts(d)) or "-")
            ws2.append([row.get("patient_id"), row.get("source_image"), no, system, doctor, parts,
                        {"correct": "Benar", "incorrect": "Salah"}.get(d.get("doctorVerdict"), "-")]
                       + list(fmt_attrs(d.get("attributes"))) + list(fmt_attrs(attrs)) + [source or "-"])
    for sheet in (ws, ws2):
        for cell in sheet[1]:
            cell.font = Font(bold=True)


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


def _coco_extras(d, label_mode):
    extra = {}
    attrs, source = cell_attributes(d, label_mode)
    if attrs:
        extra["attributes"] = {"ukuran": attrs.get("ukuran"), "warna": attrs.get("warna"), "bentuk": attrs.get("bentuk") or []}
        extra["attributes_source"] = source
    parts = corrected_parts(d)
    if parts:
        extra["corrected_by_doctor"] = parts
    if d.get("manual"):
        extra["added_by_doctor"] = True
    return extra


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
                # Field tambahan sesudah v0.1.0, hanya bila ada isinya.
                **_coco_extras(d, detail.get("labelMode", "single")),
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


# ---------------------------------------------------------------------------
# File perbandingan sistem dan dokter (F15, docs/use-case.md bagian 5)
# ---------------------------------------------------------------------------
@segmentation_bp.route("/api/segmentation/export-comparison", methods=["POST"])
def api_segmentation_export_comparison():
    """Satu xlsx per batch (folder): sheet Perbandingan (blok per gambar, format
    seperti label-asli.xlsx), Ringkasan (per pasien + total), dan Matriks."""
    data = request.json or {}
    folder = (data.get("folder") or "").strip()
    patient_id_filter = (data.get("patientId") or "").strip()
    if not folder or not os.path.isdir(folder):
        return jsonify({"ok": False, "message": "Folder tidak valid."}), 400
    rows = _latest_segmentation_rows(folder)
    if patient_id_filter:
        rows = [r for r in rows if safe_slug(r.get("patient_id") or "") == safe_slug(patient_id_filter)]
    details = load_details(folder, rows)
    if not details:
        return jsonify({"ok": False, "message": "Tidak ada hasil yang cocok untuk dibandingkan."}), 400

    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Perbandingan"
    bold = Font(bold=True)
    edge = Border(left=Side(style="thick"))
    col = 1
    for row, detail in details:
        mode = detail.get("labelMode", "single")
        has_attr = any(d.get("attributes") or d.get("correctedAttributes") for d in detail.get("detections") or [])
        heads = (["no.", "Saya: Ukuran", "Saya: Bentuk", "Saya: Warna", "Pendapat Saya",
                  "Dokter: Ukuran", "Dokter: Bentuk", "Dokter: Warna", "Pendapat Dokter"]
                 if has_attr else ["no.", "Pendapat Saya", "Pendapat Dokter"])
        ws.cell(1, col, row.get("source_image")).font = bold
        ws.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + len(heads) - 1)
        for k, h in enumerate(heads):
            c = ws.cell(2, col + k, h)
            c.font = bold
            c.alignment = Alignment(wrap_text=True)
        for r, (no, d, system, doctor) in enumerate(comparison_cells(detail), start=3):
            if has_attr:
                attrs, source = cell_attributes(d, mode)
                mine = fmt_attrs(None if d.get("manual") else d.get("attributes"))
                theirs = (fmt_attrs(attrs) if source and source.startswith("dokter")
                          else ("-", "-", "-") if d.get("deletedByDoctor") or doctor == "belum direview"
                          else ("tidak dinilai",) * 3)
                values = [no, *mine, system, *theirs, doctor]
            else:
                values = [no, system, doctor]
            for k, v in enumerate(values):
                ws.cell(r, col + k, v)
        for r in range(1, ws.max_row + 1):
            ws.cell(r, col).border = edge
        for k in range(len(heads)):
            ws.column_dimensions[get_column_letter(col + k)].width = 7 if k == 0 else 16
        col += len(heads) + 1
    ws.freeze_panes = "A3"

    # Ringkasan per pasien + total batch
    ws2 = wb.create_sheet("Ringkasan")
    ws2.append(["ID Pasien", "Gambar", "Sel dinilai dokter", "Setuju", "% kesepakatan", "Kappa",
                "Dihapus dokter", "Ditambah dokter", "Eritrosit (tanpa Uncategorised)"])
    groups = {}
    for row, detail in details:
        groups.setdefault(row.get("patient_id") or "?", []).append(detail)
    for pid, ds in sorted(groups.items()) + [("Total batch", [d for _, d in details])]:
        pairs = agreement_pairs(ds)
        agree = sum(1 for a, b in pairs if a == b)
        cells = [d for detail in ds for d in detail.get("detections") or []]
        ws2.append([pid, len(ds), len(pairs), agree, pct(agree, len(pairs)), cohen_kappa(pairs),
                    sum(1 for d in cells if d.get("deletedByDoctor")),
                    sum(1 for d in cells if d.get("manual") and not d.get("deletedByDoctor")),
                    rbc_count(ds)])
    ws2.append([])
    ws2.append(["Kesepakatan dan kappa dihitung atas sel model yang sudah dinilai dokter (verdict, koreksi, "
                "atau dihapus); sel tambahan dokter dan sel belum direview tidak ikut."])

    # Matriks sistem (baris) x dokter (kolom)
    ws3 = wb.create_sheet("Matriks")
    added_row, deleted_col = "ditambah dokter", "dihapus dokter"
    cols = RBC_CLASS_LABELS + [deleted_col]
    ws3.append(["Sistem \\ Dokter"] + cols)
    counts = {}
    all_details = [d for _, d in details]
    for system, doctor in agreement_pairs(all_details):
        key = (system, deleted_col if doctor == DELETED else doctor)
        counts[key] = counts.get(key, 0) + 1
    for detail in all_details:
        for _, d, _, doctor in comparison_cells(detail):
            if d.get("manual") and not d.get("deletedByDoctor"):
                counts[(added_row, doctor)] = counts.get((added_row, doctor), 0) + 1
    for system in RBC_CLASS_LABELS + [added_row]:
        ws3.append([system] + [counts.get((system, c), 0) or None for c in cols])
    for sheet in (ws2, ws3):
        for cell in sheet[1]:
            cell.font = bold
        for col_cells in sheet.columns:
            sheet.column_dimensions[col_cells[0].column_letter].width = 16
    ws2.column_dimensions["A"].width = 18

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_patient = safe_slug(patient_id_filter) if patient_id_filter else "batch"
    filename = f"perbandingan_sistem_dokter_{safe_patient}_{timestamp}.xlsx"
    export_path = os.path.join(folder, filename)
    suffix = 0
    while os.path.exists(export_path):
        suffix += 1
        filename = f"perbandingan_sistem_dokter_{safe_patient}_{timestamp}-{suffix}.xlsx"
        export_path = os.path.join(folder, filename)
    try:
        wb.save(export_path)
    except OSError as e:
        return jsonify({"ok": False, "message": f"Gagal menyimpan file perbandingan: {e}"}), 500
    return jsonify({"ok": True, "path": export_path, "filename": filename})
