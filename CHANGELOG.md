# Changelog

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/) dan penomoran [SemVer](https://semver.org/lang/id/).

## [Unreleased]

Target rilis 0.2.0: refactor backend tanpa mengubah perilaku (lihat `docs/refactor/`). Frontend tidak berubah; ditulis ulang di 0.3.0.

### Changed
- `app.py` (2.383 baris) dipecah menjadi `config.py`, `csvlog.py`, `quality.py`, `camera.py`, `capture.py` (blueprint `capture_bp`), `utils.py`, dan paket `segmentation/` (blueprint `segmentation_bp`: `mock_model.py`, `storage.py`, `routes.py`, `export.py`). `app.py` tinggal 42 baris.
- Kode dipindah apa adanya: 90 definisi top-level v0.1.0 ada dengan teks identik, 29 route dengan URL, method, dan fungsi yang sama.

### Changed (UI, branch `feat/ui-v0.3.0`, target 0.3.0)
- Tampilan ditulis ulang mengikuti prototipe (`docs/ui/`): dua layar (Akuisisi, Analisis sel) dengan navigasi tahap, bar sesi, bar status, tema terang/gelap, font Atkinson Hyperlegible offline, tanpa scroll halaman.
- Akuisisi: status fokus juga tampil di atas stream, tanda prasyarat (kamera, inisial, folder), alasan tombol Simpan mati ditulis.
- Analisis: inspektur sel dengan tombol kelas dan verdict besar untuk layar sentuh, shortcut B (Benar) dan S (Salah) yang langsung pindah ke sel berikutnya, tombol "Tandai sisanya benar" juga di inspektur (alur v0.1.0: tandai yang salah, sisanya disetujui sekaligus), banner "alat bantu, bukan diagnosis" dan status model mock yang mencolok. Laporan/export dan pengaturan model pindah ke dialog.
- Galat: bar galat persisten (judul "Gagal", tidak hilang sendiri) dengan tombol pemulihan (Coba hubungkan lagi, Sambungkan ulang kamera, Pilih lokasi lain, Coba simpan lagi). Server mati tampil sebagai "Terputus dari aplikasi" dan hilang sendiri saat tersambung lagi; tombol tidak macet dalam keadaan mati.
- Ambil citra saat citra sebelumnya belum disimpan kini bertanya dulu (Simpan dulu, Buang, Batal).
- Penghitung "Tersimpan sesi ini" menghitung citra sesi, terpisah dari nomor iterasi.
- `/api/save` menyebut penyebab gagal (folder hilang, disk penuh, izin, gagal tulis) dalam field `code` dan `message`, dan menulis PNG lewat `cv2.imencode` sehingga path non-ASCII di Windows tidak gagal diam-diam.
- `/api/camera/status` menambah field `frozen` (stream beku: isi frame tidak berubah lebih dari 5 detik); UI menampilkan peringatan dengan tombol sambung ulang.
- Tes baru `tests/test_galat.py` (7 tes).
- `static/js/app.js` dipecah apa adanya menjadi `common.js`, `capture.js`, `segmentation.js`, `main.js`. Backend tidak berubah.

### Added
- Tes karakterisasi `tests/test_v010.py` (14 tes) dengan acuan `tests/expected_v0.1.0.json`, termasuk data akuisisi lama di `tmp/data-uji/` (tidak di-commit).

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
