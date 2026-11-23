"""Semantik per sel untuk export: kelas akhir, koreksi dokter, atribut dan sumbernya.

Dipakai Excel laporan, COCO, file perbandingan sistem-dokter (F15), dan laporan
pasien, supaya aturannya satu sumber (padanan correctedParts di segmentation.js).

Sumber atribut (keputusan pengguna 2026-11-23): kalau model mengeluarkan atribut
tetapi dokter menilai sel lewat mode Satu kelas, atribut model disimpan tetapi
ditandai "model, tidak dinilai dokter" dan tidak dihitung benar/salah per atribut.
"""

import json
import os

from attributes import BENTUK
from config import RBC_CLASS_LABELS

DELETED = "bukan sel / dihapus"
NOT_DETECTED = "tidak terdeteksi"
NOT_REVIEWED = "belum direview"


def final_label(d):
    return d.get("correctedClassLabel") or d.get("classLabel")


def corrected_parts(d):
    """Bagian hasil model yang ditimpa dokter: kelas, ukuran, warna, bentuk."""
    if d.get("manual"):
        return []
    parts = []
    idx = d.get("correctedClassIndex")
    if idx is not None and idx != d.get("classIndex"):
        parts.append("kelas")
    m, c = d.get("attributes"), d.get("correctedAttributes")
    if m and c:
        for key in ("ukuran", "warna"):
            if (m.get(key) or None) != (c.get(key) or None):
                parts.append(key)
        if sorted(m.get("bentuk") or []) != sorted(c.get("bentuk") or []):
            parts.append("bentuk")
    return parts


def judged(d):
    """Sudah dinilai dokter: diberi verdict, dikoreksi, dihapus, atau ditambah."""
    return bool(d.get("doctorVerdict") or corrected_parts(d) or d.get("deletedByDoctor") or d.get("manual"))


def cell_attributes(d, label_mode="single"):
    """(atribut, sumber) yang berlaku untuk sel ini; (None, None) bila tidak ada atribut."""
    if d.get("correctedAttributes"):
        return d["correctedAttributes"], "dokter"
    a = d.get("attributes")
    if not a:
        return None, None
    if label_mode == "attributes" and d.get("doctorVerdict") == "correct":
        return a, "dokter (setuju model)"
    if judged(d):
        return a, "model, tidak dinilai dokter"
    return a, "model"


def fmt_attrs(a):
    """(ukuran, bentuk, warna) sebagai teks untuk tabel."""
    if not a:
        return "-", "-", "-"
    return a.get("ukuran") or "tidak diketahui", " + ".join(a.get("bentuk") or []) or "normal", a.get("warna") or "tidak diketahui"


def attribute_stats(attr_list):
    """Proporsi atribut dari daftar atribut efektif (sel tanpa atribut tidak dihitung)."""
    attrs = [a for a in attr_list if a]
    n = len(attrs)
    stats = {"n": n, "ukuran": {}, "hipokrom": 0, "bentuk": {b: 0 for b in BENTUK}}
    for a in attrs:
        key = a.get("ukuran") or "tidak diketahui"
        stats["ukuran"][key] = stats["ukuran"].get(key, 0) + 1
        stats["hipokrom"] += 1 if a.get("warna") == "hipokrom" else 0
        for b in a.get("bentuk") or []:
            if b in stats["bentuk"]:
                stats["bentuk"][b] += 1
    return stats


def pct(k, n):
    return round(100.0 * k / n, 1) if n else 0.0


def cohen_kappa(pairs):
    """Kappa Cohen dua penilai (sistem, dokter) atas pasangan label. None bila tidak terdefinisi."""
    n = len(pairs)
    if not n:
        return None
    po = sum(1 for a, b in pairs if a == b) / n
    cats = {x for p in pairs for x in p}
    pe = sum((sum(1 for a, _ in pairs if a == c) / n) * (sum(1 for _, b in pairs if b == c) / n) for c in cats)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else None


def load_details(folder, rows):
    """(baris log, isi file detail) per hasil terbaru; file hilang/rusak dilewati."""
    out = []
    for row in sorted(rows, key=lambda r: (r.get("patient_id") or "", r.get("source_image") or "")):
        try:
            with open(os.path.join(folder, row.get("detail_file") or ""), encoding="utf-8") as f:
                out.append((row, json.load(f)))
        except (OSError, ValueError):
            continue
    return out


def comparison_cells(detail):
    """Baris perbandingan satu gambar: (no, sel, kelas sistem, kelas dokter).
    Nomor = nomor sel di overlay (urutan sel yang tidak dihapus); sel dihapus di akhir."""
    dets = detail.get("detections") or []
    active = [d for d in dets if not d.get("deletedByDoctor")]
    rows = []
    for i, d in enumerate(active):
        system = NOT_DETECTED if d.get("manual") else d.get("classLabel")
        doctor = final_label(d) if judged(d) else NOT_REVIEWED
        rows.append((i + 1, d, system, doctor))
    for d in dets:
        if d.get("deletedByDoctor"):
            rows.append(("dihapus", d, d.get("classLabel"), DELETED))
    return rows


def agreement_pairs(details):
    """Pasangan (sistem, dokter) untuk kesepakatan dan kappa: sel model yang sudah dinilai dokter."""
    pairs = []
    for detail in details:
        for _, d, system, doctor in comparison_cells(detail):
            if not d.get("manual") and doctor != NOT_REVIEWED:
                pairs.append((system, doctor))
    return pairs


def rbc_count(details):
    """Eritrosit sesudah review: sel tidak dihapus, kelas akhir selain Uncategorised."""
    return sum(
        1 for detail in details for d in detail.get("detections") or []
        if not d.get("deletedByDoctor") and final_label(d) in RBC_CLASS_LABELS and final_label(d) != "Uncategorised"
    )
