"""Penulisan log CSV (capture_log.csv, segmentation_log.csv): lock global dan migrasi kolom."""

import csv
import os
import threading

from config import LOG_FILENAME


# Lindungi critical section /api/save (hitung iterasi + tulis file + tulis
# log CSV) dari race condition kalau ada dua request /api/save nyaris
# bersamaan (Flask jalan threaded=True) -- tanpa ini, dua request bisa saja
# baca "iterasi berikutnya" yang sama sebelum salah satu selesai menulis,
# jadi filename ketimpa/duplikat atau baris CSV keselip.
save_lock = threading.Lock()


# Lindungi penulisan file detail JSON + baris segmentation_log.csv dari race
# condition kalau ada beberapa "Simpan Hasil" nyaris bersamaan -- pola yang
# sama dengan save_lock di atas.
segmentation_log_lock = threading.Lock()


def _ensure_log_columns(log_path, fieldnames):
    """Migrasi in-place kalau segmentation_log.csv yang sudah ada (dari versi
    lama) belum punya kolom baru (mis. is_duplicate/duplicate_of) -- baca
    semua baris lama, rewrite dengan header terbaru (kolom baru diisi kosong
    utk baris lama), biar CSV tetap satu format konsisten & nggak ada nilai
    ke-shift/hilang pas dibuka di Excel setelah kolom baru ditambahkan.
    Harus dipanggil di dalam segmentation_log_lock."""
    if not os.path.isfile(log_path):
        return
    with open(log_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = list(reader)
    if not header or all(name in header for name in fieldnames):
        return  # file kosong, atau sudah punya semua kolom yg dibutuhkan
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row.pop(None, None)  # buang overflow restkey (baris lama yg kolomnya beda)
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def log_capture_csv(folder, row):
    """Tambahkan satu baris metadata ke capture_log.csv di folder tujuan."""
    log_path = os.path.join(folder, LOG_FILENAME)
    is_new = not os.path.exists(log_path)
    # Kolom setelah focus_score ditambahkan belakangan (kualitas fokus per tile
    # + skor CLIP opsional). focus_score tetap variance Laplacian lama supaya
    # log lama masih sebanding; tile_*/rel_*/clip_* untuk kalibrasi nanti.
    fieldnames = [
        "timestamp", "patient_id", "filename", "iterasi",
        "camera", "resolution", "focus_score",
        "tile_median", "tile_low", "tile_center", "tile_edge", "tile_valid_frac",
        "edge_ratio", "edge_warn",
        "rel_low", "rel_median", "focus_status", "tile_map_json",
        "clip_kepadatan", "clip_gabungan_v2", "clip_norm", "clip_model",
    ]
    if not is_new:
        # Migrasi in-place kalau capture_log.csv dari versi lama belum punya
        # kolom baru (dipanggil di dalam save_lock oleh api_save).
        _ensure_log_columns(log_path, fieldnames)
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if is_new:
            writer.writeheader()
        writer.writerow(row)
