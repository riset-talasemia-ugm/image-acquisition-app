# Changelog

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/) dan penomoran [SemVer](https://semver.org/lang/id/).

## [Unreleased]

Rencana: refactor struktur kode tanpa mengubah perilaku (lihat `docs/refactor/`). Target rilis 0.2.0.

## [0.1.0] - 2026-11-23

Baseline sebelum refactor. Kode berbentuk monolith: `app.py`, `static/js/app.js`, `static/css/style.css`, `templates/index.html`.

### Tab Capture
- Daftar kamera dan koneksi kamera: DirectShow (Windows), V4L2 (Linux), dan fallback SDK ToupCam (Linux/Jetson, x64/arm64).
- Stream MJPEG, pengaturan resolusi, dialog setelan kamera, deteksi kamera terputus.
- Capture frame diam, deteksi frame kosong, skor fokus Laplacian (lama).
- Kualitas fokus seluruh frame: Tenengrad per tile 8x6 relatif terhadap puncak tile, konfirmasi puncak, reset otomatis saat lapang pandang berganti, peringatan pinggir lemah.
- Skor semantik CLIP (opsional, `CLIP_QUALITY=1`).
- Save ke folder pilihan dengan nama `<id>_<YYYYMMDD-HHMMSS>_<NN>.png` dan baris di `capture_log.csv` (migrasi kolom otomatis).
- Ringkasan folder per pasien, galeri sesi dengan preview, zoom, dan navigasi.
- Shortcut keyboard Spasi/Enter.

### Tab Segmentasi
- Pilih gambar atau kirim dari Capture, isi otomatis ID pasien dari nama file.
- Segmentasi instance 13 kelas morfologi RBC. **Model masih mock (acak)**.
- Overlay mask, zoom/pan, nomor sel, highlight per kelas, ambang confidence rendah.
- Koreksi manual: ubah kelas, tambah/hapus/resize sel, koreksi massal, verdict dokter, "Tandai Sisanya Benar".
- Simpan hasil (JSON detail + `segmentation_log.csv`) dengan deteksi hasil duplikat.
- Muat hasil, daftar hasil per folder, batch per folder.
- Ringkasan per pasien (tabel dan grafik), export laporan Excel, export dataset COCO.
- Konfigurasi path model (`model_config.json`).

### Dokumentasi
- README dan panduan pengguna (`docs/panduan-aplikasi.md`/`.pdf`).
