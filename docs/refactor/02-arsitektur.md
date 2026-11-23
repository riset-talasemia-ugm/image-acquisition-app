# Arsitektur: v0.1.0 dan Target Refactor

> **Status 2026-11-23:** target backend (bagian 2.1) sudah tercapai di branch `refactor/v0.2.0` (Fase 1 selesai). Bedanya dengan rencana:
> - `log_capture_csv` masuk ke `csvlog.py`, bukan `capture.py`, karena ia memanggil `_ensure_log_columns`;
> - `utils.py` ditambahkan untuk `safe_slug` dan `frame_to_png_base64`, yang dipakai capture dan segmentasi;
> - `segmentation/routes.py` 660 baris, sedikit di atas patokan.
>
> Frontend (bagian 2.2) tidak dikerjakan di v0.2.0, karena ditulis ulang di v0.3.0. Struktur frontend v0.3.0 yang dipakai (lebih sederhana dari bagian 2.2: empat file JS, satu CSS) ada di `docs/ui/02-rencana-v0.3.0.md`.

## 1. Kondisi sekarang (v0.1.0)

Semua kode ada di empat file:

| File | Baris | Isi |
|---|---|---|
| `app.py` | ~2.380 | Konstanta, kamera, fokus, CLIP, capture/save, segmentasi, export, konfigurasi model, dan semua route |
| `static/js/app.js` | ~2.230 | Seluruh logika UI kedua tab, state global, event listener |
| `static/css/style.css` | ~640 | Semua gaya |
| `templates/index.html` | ~510 | Markup kedua tab, memuat `app.js` dan `style.css` |

### Peta isi `app.py` (perkiraan baris)

| Baris | Bagian |
|---|---|
| 1-230 | Import, konstanta (`FOCUS_*`, `CLIP_*`, `RBC_CLASS_*`, nama log), lock, `_ensure_log_columns` |
| 231-594 | Loader SDK ToupCam, `CameraManager` |
| 595-640 | Helper: `next_iteration_from_folder`, `gen_mjpeg`, `frame_to_png_base64`, `safe_slug` |
| 641-805 | Fokus: tile Tenengrad, `FocusTracker`, `analyze_focus` |
| 806-910 | `ClipQuality` (opsional) |
| 911-960 | `resize_for_save`, `is_blank_frame`, `log_capture_csv` |
| 961-1250 | Route halaman, kamera, capture, fokus, folder, save |
| 1253-1318 | Mock segmentasi |
| 1319-1974 | Route segmentasi: run, load, list, save, batch, check, summary |
| 1975-2306 | Export Excel dan COCO |
| 2307-2383 | Konfigurasi model dan `app.run()` |

### Peta isi `app.js`

| Baris | Bagian |
|---|---|
| 1-150 | Referensi DOM dan state global (`seg*`, `selectedFolder`, dst.) |
| 152-197 | Toast, modal pilihan/konfirmasi |
| 198-332 | Kamera |
| 333-544 | Kartu kualitas fokus dan CLIP |
| 545-837 | Capture, pilih folder, galeri/preview, ringkasan folder, save |
| 838-1048 | Tab, legenda/ringkasan/grafik kelas |
| 1049-1139 | Zoom dan pan |
| 1140-1431 | Tambah/hapus/resize sel, pilih dan muat gambar/hasil |
| 1432-1722 | Overlay, daftar deteksi, run, simpan |
| 1723-1974 | Ringkasan pasien, export, daftar hasil, batch |
| 1975-2078 | Koreksi massal, konfigurasi model |
| 2079-2228 | Shortcut keyboard, inisialisasi |

### Catatan sejarah
- Branch `refactor/modularize-backend-frontend` dan `refactor/sync-modular` sudah pernah memecah kode ini, tetapi keduanya bercabang dari `454ce22` dan **tidak memuat** fitur yang datang sesudahnya: alat review segmentasi, export COCO, fokus tile, dan CLIP. File modularnya juga sudah dihapus dari `main` (`2300488`).
- Karena itu, refactor dimulai ulang dari v0.1.0. Kedua branch lama cukup dipakai sebagai contoh pembagian modul dan tidak di-merge.

## 2. Target (v0.2.0)

Prinsipnya: pecah per domain, pindahkan kode **apa adanya**, dan jangan menambah lapisan abstraksi baru. Tiap file harus bisa dibaca sendiri dan tidak melebihi ~600 baris.

### 2.1 Backend

```
app.py                  # buat Flask app, daftarkan blueprint, route "/", app.run()
config.py               # semua konstanta + env var (FOCUS_*, CLIP_*, RBC_CLASS_*, nama log)
csvlog.py               # _ensure_log_columns + lock global (save_lock, segmentation_log_lock)
camera.py               # loader ToupCam, CameraManager, instance global `camera`, gen_mjpeg
quality.py              # fokus tile, FocusTracker, analyze_focus, ClipQuality, is_blank_frame
capture.py              # Blueprint: /api/cameras, /api/camera/*, /stream, /api/capture*, /api/focus/*,
                        #   /api/quality/status, /api/select-folder, /api/save, /api/folder-summary
segmentation/
  __init__.py           # Blueprint segmentation_bp (url_prefix /api/segmentation)
  mock_model.py         # generate_mock_instance_segmentation  (nanti diganti model sungguhan)
  storage.py            # baca/tulis JSON detail, segmentation_log.csv, deteksi duplikat
  routes.py             # route run/load/list/save/batch/check/summary/model-*
  export.py             # export Excel + COCO
tests/                  # lihat 04-rencana-uji.md
```

Aturan:
- **Satu instance global tetap satu.** `camera`, `FocusTracker`, `ClipQuality`, dan kedua lock dibuat sekali di modulnya, lalu di-import modul lain. Jangan membuat salinannya.
- Nama route dan URL tidak berubah. Blueprint hanya memindahkan lokasi definisi route.
- `config.py` hanya berisi nilai. Tidak ada class Config atau loader YAML.
- Kamera dan route capture boleh tetap satu file (`capture.py`) kalau pemisahannya malah menambah import silang. Ukuran file yang menentukan, bukan aturan "satu domain satu file".

### 2.2 Frontend

Tetap tanpa build step. Rekomendasinya adalah **script klasik berurutan**, bukan ES module:

```html
<script defer src="js/core.js"></script>        <!-- state global, DOM ref, toast, modal -->
<script defer src="js/camera.js"></script>
<script defer src="js/focus.js"></script>       <!-- kartu fokus + CLIP -->
<script defer src="js/capture.js"></script>     <!-- capture, save, galeri, ringkasan folder -->
<script defer src="js/seg-view.js"></script>    <!-- tab, legenda, grafik, zoom/pan, overlay -->
<script defer src="js/seg-edit.js"></script>    <!-- tambah/hapus/resize, koreksi massal, verdict -->
<script defer src="js/seg-data.js"></script>    <!-- run, simpan, muat, batch, ringkasan, export, model -->
<script defer src="js/main.js"></script>        <!-- shortcut keyboard + inisialisasi -->
```

Alasannya:
- Variabel `let`/`const` level atas di script klasik berbagi scope global yang sama. Kode bisa dipindah file tanpa menulis `import`/`export`, sehingga risiko salah wiring paling kecil.
- Urutan eksekusinya mengikuti urutan tag (dijamin oleh `defer`), sama seperti satu file sekarang.
- ES module bisa diadopsi nanti kalau memang butuh isolasi. Branch lama yang mencoba ES module sekaligus justru sulit disinkronkan.

### 2.3 CSS

```
css/base.css          # variabel warna, layout umum, tombol, toast
css/capture.css       # tab Capture, kartu fokus, galeri, preview
css/segmentation.css  # tab Segmentasi, overlay, daftar sel, grafik
css/modal.css         # modal
```

Urutan `<link>` harus sama dengan urutan blok di `style.css` sekarang, supaya hasil cascade tidak berubah.

## 3. Yang sengaja tidak dilakukan

- Tidak pindah ke framework lain (FastAPI, React, dsb.).
- Tidak menambah dependency baru. Tes cukup memakai `unittest` bawaan dan test client Flask (lihat 04).
- Tidak mengubah nama fungsi, nama field JSON, nama kolom CSV, atau teks UI.
- Tidak memperbaiki bug atau menyetel ulang ambang di tengah refactor. Temuan dicatat dulu, lalu dikerjakan setelah v0.2.0.
