"""Atribut sel (ukuran, bentuk, warna) untuk model multi-label, dan kelas turunannya.

Kontrak (docs/use-case.md bagian 7): deteksi boleh punya field opsional
`attributes` = {"ukuran": "mikrosit"|"normosit"|"makrosit"|None,
"warna": "normokrom"|"hipokrom"|None, "bentuk": [kelompok, ...]}, sama dengan
keluaran eksperimen ../sardjito-atribut-eksperimen (COCO `attributes`).
`bentuk` kosong = bentuk normal; `ukuran` None = tidak diketahui.
`classIndex` tetap diisi kelas turunan supaya semua hitungan, laporan, dan
export yang memakai satu kelas tetap jalan.

Sumber aturan (disalin, bukan diimpor, karena aplikasi berjalan sendiri di Jetson):
- resolve_class: ../tambahan-dataset/skrip/overlay_jenis_sel.py, commit 073b2cc (2026-11-22)
- kelompok bentuk dan kelas_turunan: ../tambahan-dataset/skrip/atribut_sel.py, branch
  atribut-sel (belum di-commit saat disalin, 2026-11-23)
Kalau aturan di repo dataset berubah, salin ulang dan perbarui tes test_atribut.py.
"""

from config import RBC_CLASS_LABELS

UKURAN = ["mikrosit", "normosit", "makrosit"]
WARNA = ["normokrom", "hipokrom"]

# Kelompok bentuk = nama kelas 16 dataset Sardjito -> ID kelas dataset.
BENTUK = {
    "Spherocyte": 3, "Target": 4, "Stomatocyte": 5, "Ovalocyte": 6, "Teardrop": 7,
    "Burr": 8, "Schistocyte": 9, "Elliptocyte": 12, "Bite": 13, "Blister": 14,
}

# ID 0-12 sama di dataset dan aplikasi. ID 13-15 (Bite, Blister, Microcytic
# Hypochromia) belum ada di 13 kelas aplikasi.
# ponytail: pemetaan sementara sampai daftar kelas final diputuskan (menunggu
# ../sardjito-rbc-eksperimen); bila aplikasi memakai 16 kelas, hapus pemetaan ini.
DATASET_KE_APLIKASI = {13: 9, 14: 9, 15: 11}


def resolve_class(hypo, shape, size, overlap):
    """Aturan kelas (single label): hipokrom hanya menang atas ovalosit/ellips/normal, karena bentuk itu masih
    terbaca dari rasio sumbu mask. Bentuk lain (target, stomatosit, teardrop, burr, skistosit, bite, blister,
    sferosit) menang atas hipokrom. Lalu hipokrom+mikrosit -> 15; hipokrom -> 11; bentuk > ukuran > bertumpuk > normal."""
    if hypo:
        keep = [s for s in shape if s not in (6, 12, 10)]  # 10 = teks tak dikenal: hipokrom tetap menang
        return keep[0] if keep else 15 if 2 in size else 11
    return shape[0] if shape else size[0] if size else 10 if overlap else 0


def clean(attrs):
    """Rapikan atribut dari model atau dari review dokter; nilai tak dikenal dibuang. None kalau bukan dict."""
    if not isinstance(attrs, dict):
        return None
    ukuran = attrs.get("ukuran") if attrs.get("ukuran") in UKURAN else None
    warna = attrs.get("warna") if attrs.get("warna") in WARNA else None
    bentuk = [b for b in (attrs.get("bentuk") or []) if b in BENTUK]
    return {"ukuran": ukuran, "warna": warna, "bentuk": list(dict.fromkeys(bentuk))}


def derived_class_index(attrs):
    """Atribut -> indeks kelas aplikasi (RBC_CLASS_LABELS), lewat resolve_class seperti kelas_turunan."""
    a = clean(attrs) or {"ukuran": None, "warna": None, "bentuk": []}
    size = {"mikrosit": [2], "makrosit": [1]}.get(a["ukuran"], [])
    dataset_id = resolve_class(a["warna"] == "hipokrom", [BENTUK[b] for b in a["bentuk"]], size, False)
    index = DATASET_KE_APLIKASI.get(dataset_id, dataset_id)
    return index if 0 <= index < len(RBC_CLASS_LABELS) else RBC_CLASS_LABELS.index("Uncategorised")
