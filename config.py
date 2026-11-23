"""Konstanta dan env var aplikasi. Hanya nilai, tanpa logika."""

import os

# Untuk deteksi buram (variance of Laplacian; skor ~6 = fokus baik pada kamera mikroskop saat ini)
FOCUS_BLUR_THRESHOLD = 5.0

# untuk deteksi objek tidak ada
BLANK_STD_THRESHOLD = 5.0

# ---------------------------------------------------------------------------
# Kualitas fokus per tile di SELURUH frame
# ---------------------------------------------------------------------------
# Keputusan sementara dari eksperimen CLIP (lihat ringkasan-eksperimen-clip.md
# di folder induk): fokus dinilai dengan Tenengrad per tile di seluruh frame
# (dokter menganotasi citra penuh, jadi pinggir frame juga harus tajam) --
# BUKAN variance Laplacian (dominan noise sensor) dan bukan CLIP.
#
# Nilai Tenengrad per tile sangat bergantung pada isi tile (sel padat vs
# jarang), jadi nilai mentah TIDAK dibandingkan antar lapang pandang. Yang
# dipakai adalah nilai RELATIF terhadap puncak tiap tile selama fokus diputar
# di lapang pandang yang sama (peak-hold per tile, lihat FocusTracker).
FOCUS_TILE_COLS = 8
FOCUS_TILE_ROWS = 6
# Tile dengan std abu-abu di bawah ini dianggap latar kosong dan tidak dihitung.
# Angka ini perkiraan dari noise sensor (~0,5) + gradien iluminasi; pada data
# 27-08 hampir semua tile berisi sel (std >= 4) sehingga belum bisa
# dikalibrasi dari data.
FOCUS_TILE_MIN_STD = 3.0
FOCUS_LOW_PERCENTILE = 25
# Puncak baru dianggap TERKONFIRMASI kalau setelah puncak itu median Tenengrad
# pernah turun sampai <= FOCUS_PEAK_DROP x puncak (operator sudah memutar fokus
# melewati titik tajam). Tanpa ini, saat fokus diputar menuju tajam tiap frame
# menjadi puncak baru sehingga selalu "100% dari puncak" padahal belum tajam.
# Kenaikan di bawah FOCUS_PEAK_TOL dianggap noise, bukan puncak baru.
FOCUS_PEAK_DROP = 0.90
FOCUS_PEAK_TOL = 0.02
# Kalau korelasi citra kasar (64x48) dengan citra referensi turun di bawah ini,
# dianggap pindah lapang pandang -> puncak di-reset otomatis.
FOCUS_FIELD_CHANGE_NCC = 0.5
# Ambang status (relatif terhadap puncak tile, persentil ke-25 semua tile).
# MASIH HEURISTIK, belum dikalibrasi dengan label dokter: nilai mentahnya
# dicatat di capture_log.csv untuk kalibrasi nanti.
FOCUS_REL_GOOD = 0.85
FOCUS_REL_WARN = 0.65
# Peringatan (petunjuk saja, TIDAK mengubah status): Tenengrad rata-rata tile
# pinggir dibagi tile dalam. Status di atas hanya menilai setelan fokus
# (dekat puncak tile masing-masing), jadi pinggir yang buram bawaan (mis.
# kemiringan preparat/kamera) tidak terlihat olehnya; rasio ini satu-satunya
# sinyal satu-frame untuk itu. 0,65 = persentil ke-25 rasio di 80 gambar data
# 27-08 (menandai ~29% gambar; gambar pasien-1 yang pinggirnya terlihat buram
# bernilai 0,646). Masih heuristik: sel yang lebih jarang di pinggir juga
# menurunkan rasio tanpa ada blur.
FOCUS_EDGE_RATIO_WARN = 0.65

# ---------------------------------------------------------------------------
# Skor semantik CLIP (opsional, eksperimen)
# ---------------------------------------------------------------------------
# Nonaktif kecuali environment variable CLIP_QUALITY=1 dan paket torch +
# open_clip_torch terpasang (lihat requirements-clip.txt). Hanya dihitung saat
# Capture, tidak per frame. Skor ini BELUM divalidasi dengan label dokter:
# ditampilkan dan dicatat ke log, bukan dipakai sebagai gerbang.
CLIP_ENABLED = os.environ.get("CLIP_QUALITY", "0").strip() == "1"
CLIP_MODEL_NAME = os.environ.get("CLIP_MODEL", "ViT-B-32")
CLIP_PRETRAINED = os.environ.get("CLIP_PRETRAINED", "openai")
# Crop 448 px pada frame selebar 2592 px (skala yang diuji di eksperimen),
# diletakkan di grid yang membentang ke SELURUH frame (termasuk tepi).
CLIP_CROP_FRAC = 448 / 2592
CLIP_GRID_COLS = 4
CLIP_GRID_ROWS = 3
_CLIP_DENSITY_PAIR = (
    "a microscope image densely covered with red blood cells",
    "a microscope image of a blood smear with a large empty background",
)
# "gabungan_v2": semantik murni, tanpa negasi dan tanpa aspek fokus.
_CLIP_POS_V2 = [
    "a microscopic image of a well-spread blood smear with evenly distributed red blood cells",
    "a high quality peripheral blood smear image with uniform cell distribution and well separated cells",
    "a clear microscopy image of blood cells in monolayer with minimal empty space",
    "a blood smear image with homogeneous red blood cell arrangement",
]
_CLIP_NEG_V2 = [
    "a blood smear image with heavily overlapping and clumped red blood cells",
    "a blood smear image with large empty background area and sparse cells",
    "a blood smear image with dust, scratches, or air bubble artifacts",
]

# Berapa kali read() OpenCV boleh gagal berturut-turut sebelum dianggap
OPENCV_DISCONNECT_THRESHOLD = 15

# Kamera "terhubung" tapi isi frame tidak berubah sama sekali selama sekian
# detik (selagi stream dibaca) dianggap beku. Sensor asli selalu punya derau,
# jadi frame identik berturut-turut berarti driver/kamera macet. Frame yang
# hampir seragam (lensa tertutup, gelap total) dikecualikan.
CAMERA_FROZEN_SECONDS = 5.0

# Capture otomatis tingkat 1 (autocapture.py). MASIH HEURISTIK: dikalibrasi di
# mikroskop asli (nilai NCC citra kasar 64x48 antar pemeriksaan ~0,7 detik).
# - Meja dianggap diam kalau NCC frame berturut-turut >= AUTO_STILL_NCC selama
#   AUTO_STILL_CHECKS pemeriksaan (memutar fokus halus tetap dihitung diam).
# - Lapang dianggap sama dengan citra tersimpan terakhir kalau NCC >= AUTO_DUPLICATE_NCC.
AUTO_STILL_NCC = 0.97
AUTO_STILL_CHECKS = 2
AUTO_DUPLICATE_NCC = 0.8

# Penjaga penyimpanan (F11): bar status memberi peringatan kalau sisa ruang di
# folder simpan di bawah ini. Satu citra 2592x1944 PNG kira-kira 10 MB, jadi
# 2 GB ~ 200 citra ~ 10 pasien.
STORAGE_WARN_BYTES = 2 * 1024 ** 3

# Cek jam saat menyala (F5): Jetson tanpa baterai jam bisa kembali ke 1970
# atau tanggal build. Tahun di bawah ini pasti salah.
CLOCK_MIN_YEAR = 2026

# Salinan citra yang belum disimpan, supaya bisa dipulihkan setelah listrik
# padam atau aplikasi tertutup (UC-10). Dihapus setelah citra disimpan.
RECOVERY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recovery")

# Sisa ruang minimum di folder tujuan sebelum menyimpan (byte), di luar
# perkiraan ukuran file PNG-nya sendiri.
SAVE_MIN_FREE_BYTES = 50 * 1024 * 1024
LOG_FILENAME = "capture_log.csv"

# Label kelas morfologi sel eritrosit untuk tab Segmentasi & Klasifikasi.
# Urutan index di sini PENTING -- ini bakal jadi mapping output model
# klasifikasi (deep learning) begitu pipeline-nya dipasang, jadi jangan
# diubah urutannya tanpa nyesuaikan juga di sisi model/training nanti.
RBC_CLASS_LABELS = [
    "Normal cell",
    "Macrocyte",
    "Microcyte",
    "Spherocyte",
    "Target cell",
    "Stomatocyte",
    "Ovalocyte",
    "Teardrop",
    "Burr cell",
    "Schistocyte",
    "Uncategorised",
    "Hypochromia",
    "Elliptocyte",
]

# Warna tampilan per kelas (dipakai buat overlay & legenda di frontend) --
# ditaruh satu sumber di backend biar konsisten kalau nanti dipakai juga di
# skrip training/evaluasi (mis. visualisasi confusion matrix per warna kelas
# yang sama).
RBC_CLASS_COLORS = [
    "#16a34a",  # Normal cell
    "#2563eb",  # Macrocyte
    "#f59e0b",  # Microcyte
    "#db2777",  # Spherocyte
    "#7c3aed",  # Target cell
    "#0891b2",  # Stomatocyte
    "#ea580c",  # Ovalocyte
    "#65a30d",  # Teardrop
    "#dc2626",  # Burr cell
    "#9333ea",  # Schistocyte
    "#64748b",  # Uncategorised
    "#ca8a04",  # Hypochromia
    "#0d9488",  # Elliptocyte
]

# File ringkasan hasil segmentasi (satu baris per proses "Simpan Hasil"),
# ditulis di folder yang sama dengan gambar sumbernya -- polanya sengaja
# dibuat mirip capture_log.csv biar gampang dianalisis bareng.
SEGMENTATION_LOG_FILENAME = "segmentation_log.csv"

# is_duplicate/duplicate_of: ditambahkan belakangan (lihat _ensure_log_columns)
# buat nandain kalau suatu hasil disimpan persis sama (jumlah sel per kelas +
# total identik) dengan hasil TERAKHIR yang sudah tersimpan buat gambar yang
# sama -- biar folder nggak numpuk file JSON duplikat tanpa keterangan.
#
# doctor_reviewed_count/doctor_correct_count/doctor_incorrect_count: agregasi
# penilaian dokter per sel (lihat doctorVerdict di detections) -- diisi 0 buat
# hasil batch (mock otomatis, tidak pernah direview satu-satu).
SEGMENTATION_LOG_FIELDNAMES = (
    ["timestamp", "patient_id", "source_image", "detail_file", "total_cells", "is_duplicate", "duplicate_of"]
    + ["doctor_reviewed_count", "doctor_correct_count", "doctor_incorrect_count"]
    + RBC_CLASS_LABELS
)

# ---------------------------------------------------------------------------
# Status & konfigurasi model segmentasi
# ---------------------------------------------------------------------------
# Placeholder transparansi -- inference model instance segmentation ASLI
# (Mask R-CNN/Detectron2) belum dipasang sama sekali (lihat
# generate_mock_instance_segmentation). File config ini cuma NYIMPAN path
# checkpoint yang direncanakan dipakai nanti, belum benar-benar memuat/
# menjalankan model apapun -- tujuannya biar plumbing-nya sudah siap begitu
# integrasi model beneran dikerjakan (tinggal baca MODEL_CONFIG_PATH di
# generate_mock_instance_segmentation/api_segmentation_run dan branch ke
# inference asli).
MODEL_CONFIG_FILENAME = "model_config.json"
MODEL_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), MODEL_CONFIG_FILENAME
)

# Ambang batas (persen) confidence sel yang dianggap "rendah" di UI (badge +
# garis putus-putus di overlay) -- disimpan di file config yang sama dengan
# modelPath biar bisa diatur dari panel "Status Model Segmentasi" tanpa perlu
# ubah kode, bukan angka mutlak yang berlaku selamanya.
DEFAULT_LOW_CONFIDENCE_THRESHOLD = 70
