# Spesifikasi Aplikasi v0.1.0 (baseline refactor)

Dokumen ini mencatat apa yang **sudah** dilakukan aplikasi v0.1.0 dan menjadi patokan refactor: setelah refactor, semua butir di sini harus tetap berlaku persis sama. Refactor tidak boleh menambah, mengurangi, atau mengubah perilaku.

## 1. Tujuan dan ruang lingkup

Aplikasi ini adalah aplikasi web lokal (Flask, `http://127.0.0.1:5000`) untuk riset talasemia, dengan dua tab:
1. **Capture**: akuisisi citra apusan darah tepi (ADT) dari kamera mikroskop USB, lengkap dengan kontrol kualitas fokus.
2. **Segmentasi**: segmentasi dan klasifikasi morfologi eritrosit (13 kelas) dan koreksi manual oleh dokter, lalu export laporan dan dataset.

Di luar lingkup v0.1.0: model segmentasi sungguhan (sekarang masih mock), autentikasi, multi-user, dan akses jaringan.

## 2. Pengguna dan lingkungan

| Item | Nilai |
|---|---|
| Pengguna | Peneliti/dokter di lab, satu orang per laptop |
| OS | Windows 10/11, Ubuntu/Linux x86_64, NVIDIA Jetson (arm64) |
| Python | 3.9+ |
| Dependensi | Flask, OpenCV, openpyxl, pygrabber + comtypes (Windows); opsional torch + open_clip |
| Jaringan | Offline, kecuali saat mengunduh bobot CLIP sekali |
| Peluncur | `run.bat`, `run-clip.bat`, `run.sh` |

## 3. Kebutuhan fungsional

### 3.1 Kamera (F-CAM)
- F-CAM-1 Menampilkan daftar kamera (DirectShow di Windows, `/dev/video*` di Linux).
- F-CAM-2 Menghubungkan kamera dengan resolusi pilihan, lalu melaporkan resolusi aktualnya.
- F-CAM-3 Fallback otomatis ke SDK ToupCam di Linux bila V4L2 gagal. Arsitektur SDK dipilih lewat `platform.machine()`.
- F-CAM-4 Stream MJPEG di `/stream`.
- F-CAM-5 Mendeteksi kamera terputus (`OPENCV_DISCONNECT_THRESHOLD = 15` kegagalan baca berturut-turut) dan memulihkan status UI setelah halaman di-reload.
- F-CAM-6 Membuka dialog setelan kamera.

### 3.2 Capture dan simpan (F-CAP)
- F-CAP-1 Capture frame diam, dengan penandaan frame kosong (`BLANK_STD_THRESHOLD`).
- F-CAP-2 Analisis fokus tile 8x6 (Tenengrad relatif terhadap puncak tiap tile): status Baik/Sedang/Buram, peta tile, peringatan pinggir lemah. Semua ambangnya ada di konstanta `FOCUS_*`.
- F-CAP-3 Polling fokus live (~0,7 detik, bisa dimatikan) dan tombol reset puncak manual. Puncak juga direset otomatis saat lapang pandang berganti.
- F-CAP-4 Skor CLIP hanya aktif bila `CLIP_QUALITY=1`. Modelnya dimuat di latar belakang.
- F-CAP-5 Memilih folder simpan lewat dialog native (tkinter).
- F-CAP-6 Save: nama file `<slug>_<YYYYMMDD-HHMMSS>_<NN>.png` dengan nomor iterasi melanjutkan isi folder, resize ke resolusi pilihan (scale down, tanpa crop), dan dilindungi `save_lock`.
- F-CAP-7 Save saat status Buram meminta konfirmasi dulu (peringatan, tidak memblokir).
- F-CAP-8 Ringkasan folder (jumlah gambar per pasien) dan galeri sesi dengan preview, zoom 100%, navigasi panah, dan Esc.
- F-CAP-9 Shortcut Spasi/Enter untuk Capture/Save, nonaktif saat preview atau modal terbuka.

### 3.3 Segmentasi (F-SEG)
- F-SEG-1 Memilih gambar sumber atau mengirimnya dari tab Capture. ID pasien ditebak dari nama file.
- F-SEG-2 Menjalankan segmentasi (mock `generate_mock_instance_segmentation`).
- F-SEG-3 Overlay polygon per sel, zoom/pan, nomor sel, highlight per kelas, dan sorotan untuk confidence di bawah ambang.
- F-SEG-4 Koreksi: ubah kelas, tambah sel manual, hapus, resize, pilih banyak sel lalu koreksi massal, verdict dokter per sel, dan "Tandai Sisanya Benar".
- F-SEG-5 Menyimpan hasil ke JSON detail dan satu baris `segmentation_log.csv`. Hasil duplikat (jumlah per kelas identik dengan hasil terakhir) terdeteksi dan perlu konfirmasi simpan paksa. Dilindungi `segmentation_log_lock`.
- F-SEG-6 Memuat hasil (lewat dialog atau path), menampilkan daftar hasil per folder dengan filter, dan mengecek hasil yang sudah ada.
- F-SEG-7 Batch: memproses semua gambar dalam satu folder.
- F-SEG-8 Ringkasan per pasien dalam bentuk tabel dan grafik batang SVG.
- F-SEG-9 Export laporan Excel dan dataset COCO.
- F-SEG-10 Status dan konfigurasi path model, serta ambang confidence rendah (default 70).

## 4. Kontrak yang wajib dipertahankan

Refactor dianggap gagal kalau salah satu kontrak ini berubah.

### 4.1 Endpoint HTTP (URL, method, bentuk JSON request/response)

| Kelompok | Endpoint |
|---|---|
| Halaman | `GET /`, `GET /stream` |
| Kamera | `GET /api/cameras`, `POST /api/camera/connect`, `POST /api/camera/settings`, `GET /api/camera/status` |
| Capture | `POST /api/capture`, `POST /api/capture/clip`, `GET /api/focus/live`, `POST /api/focus/reset-peak`, `GET /api/quality/status`, `POST /api/select-folder`, `POST /api/save`, `GET /api/folder-summary` |
| Segmentasi (`/api/segmentation/...`) | `GET classes`, `POST select-image`, `POST run`, `POST load`, `POST load-path`, `GET list-results`, `POST save`, `POST batch-select`, `POST batch-run`, `GET check-existing`, `GET patient-summary`, `POST export-report`, `POST export-coco`, `GET model-status`, `POST model-config` |

### 4.2 Format file di folder data

Data lama di laptop akuisisi harus tetap bisa dibaca.

- **Gambar capture**: `<slug>_<YYYYMMDD-HHMMSS>_<NN>.png`.
- **`capture_log.csv`**, dengan urutan kolom: `timestamp, patient_id, filename, iterasi, camera, resolution, focus_score, tile_median, tile_low, tile_center, tile_edge, tile_valid_frac, edge_ratio, edge_warn, rel_low, rel_median, focus_status, tile_map_json, clip_kepadatan, clip_gabungan_v2, clip_norm, clip_model`. File lama dimigrasi in-place oleh `_ensure_log_columns`.
- **JSON detail segmentasi**: `<base>_segmentation_<timestamp>[-N].json`, berisi `timestamp, patientId, sourceImage, detections, isDuplicate, duplicateOfFile`.
- **Deteksi** (dipakai UI, dan nanti oleh model sungguhan): `id, classIndex, classLabel, confidence, bbox [x,y,w,h], mask [[x,y],...]`, ditambah field koreksi/verdict dari frontend.
- **`segmentation_log.csv`**: `timestamp, patient_id, source_image, detail_file, total_cells, is_duplicate, duplicate_of, doctor_reviewed_count, doctor_correct_count, doctor_incorrect_count`, diikuti 13 kolom kelas.
- **`RBC_CLASS_LABELS`**: urutan 13 kelas tidak boleh berubah, karena urutan ini menjadi indeks output model.
- **`model_config.json`** di root aplikasi.

### 4.3 Konfigurasi lingkungan
Variabel lingkungannya `CLIP_QUALITY`, `CLIP_MODEL`, dan `CLIP_PRETRAINED`. Cara menjalankan (`python app.py`, `run.bat`, `run.sh`) tetap sama.

## 5. Kebutuhan non-fungsional

- NF-1 Tetap berjalan di ketiga platform (Windows, Linux x86_64, Jetson).
- NF-2 Frontend tanpa build step (tanpa npm atau bundler). Flask cukup menyajikan file statis.
- NF-3 Analisis fokus satu frame 5 MP sekitar 0,1 detik di laptop, dan refactor tidak boleh memperlambatnya.
- NF-4 Penulisan file dan log aman dari race condition. Tiap lock tetap satu instance global.
- NF-5 Teks UI dan komentar kode berbahasa Indonesia.

## 6. Batasan yang diketahui (bukan target refactor)

- Model segmentasi masih mock.
- Ambang fokus (`FOCUS_REL_GOOD/WARN`, `FOCUS_EDGE_RATIO_WARN`) masih heuristik dan belum dikalibrasi dengan label dokter.
- Belum ada tes otomatis. Tes ini dibuat di Fase 0 rencana refactor.

## Perubahan kontrak sesudah v0.1.0

Hanya penambahan field; field lama tidak berubah.

- Deteksi: field opsional `attributes` {`ukuran`, `warna`, `bentuk`} dari model multi-label dan `correctedAttributes` dari review dokter; `classIndex`/`correctedClassIndex` tetap kelas (turunan). File detail mendapat `labelMode: "attributes"` hanya untuk review mode atribut.
- Deteksi: `deletedByDoctor: true` untuk sel yang dihapus dokter (tetap di file detail, tidak dihitung di mana pun) dan `originalMask` bila ukuran sel diubah.
- `model-status`/`model-config`: field `outputType` (`single` | `attributes`).

- `GET /api/camera/status`: field `frozen` (bool), true bila stream dibaca tetapi isi frame tidak berubah lebih dari `CAMERA_FROZEN_SECONDS` (branch `feat/ui-v0.3.0`).
- `POST /api/save` saat gagal: field `code` (`folder`, `disk_full`, `permission`, `write`, `encode`) dan `message` yang menyebut penyebab. File PNG kini ditulis lewat `cv2.imencode` + `open()`; isinya sama dengan `cv2.imwrite`, tetapi path non-ASCII di Windows ikut berhasil.
- Rute baru (tercatat di `tests/test_v010.py`, `TestRoutes`):
  - `GET /api/system/status?folder=`: `bootId`, `time`, `clockSuspect`, `disk` {`path`, `free`, `total`, `low`} (F5, F11);
  - `GET|POST /api/recovery/capture`: salinan citra belum tersimpan di `recovery/` (UC-10); POST `{action: "restore"|"discard"}`;
  - `POST /api/rating/next {folder, rater, id?}` dan `POST /api/rating/submit {folder, rater, id, verdict, reasons, note}`: lembar penilaian citra (F14, `rating.py`);
  - `GET /laporan?folder=&patient=`: laporan pasien siap cetak/PDF (UC-07, `report.py`);
  - `GET|POST /api/segmentation/attributes`: kosakata atribut dan kelas turunan (persiapan model multi-label, `attributes.py`);
  - `POST /api/segmentation/open-path {path}`: buka gambar sumber tanpa dialog, bentuk respons sama dengan `select-image`.
