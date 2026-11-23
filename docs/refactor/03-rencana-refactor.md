# Rencana Refactor v0.1.0 ke v0.2.0

**Cakupan (diputuskan pengguna 2026-11-23): v0.2.0 hanya merefactor backend.** Frontend (`app.js`, `style.css`) tidak dipecah, karena akan ditulis ulang di v0.3.0 mengikuti prototipe UI. Memecah file yang akan diganti berarti kerja dua kali.

## 1. Tujuan dan kriteria selesai

**Tujuan:** memecah backend monolith (lihat `02-arsitektur.md`) **tanpa mengubah perilaku sedikit pun** (lihat `01-spesifikasi-v0.1.0.md`). Alasannya, dikonfirmasi pengguna pada 2026-11-23:
1. Model segmentasi sungguhan akan dipasang, jadi bagian inferensi harus terpisah rapi (`segmentation/mock_model.py`).
2. File terlalu besar sehingga susah dibaca dan diedit, baik oleh manusia maupun AI.
3. Akan ada orang lain yang ikut mengerjakan, jadi perlu README developer dan pembagian modul yang jelas.
4. Aplikasi akan dijalankan di Jetson/perangkat lain, jadi kinerja dan kamera harus diuji di sana.
5. Menambah fitur sering memunculkan bug, jadi tes harus dibuat lebih dulu.
6. UI/UX akan dirombak. Perombakan ini **bukan** bagian dari refactor: dikerjakan di v0.3.0 setelah v0.2.0. Frontend v0.3.0 langsung ditulis dalam struktur file baru (lihat `docs/ui/`).

Refactor dianggap selesai kalau:
1. Semua tes otomatis di `tests/` lulus, dengan hasil sama seperti di v0.1.0.
2. Checklist manual di `04-rencana-uji.md` lulus di laptop pengembangan **dan** di laptop akuisisi dengan kamera asli.
3. `app.py` tinggal berisi pembuatan app, pendaftaran blueprint, route `/`, dan `app.run()`. Frontend (`app.js`, `style.css`, `index.html`) tidak berubah dari v0.1.0.
4. Data lama (folder berisi `capture_log.csv`, `segmentation_log.csv`, JSON detail dari v0.1.0) terbaca normal.

## 2. Aturan kerja

- **Pindahkan, jangan ubah.** Tiap langkah hanya memotong-tempel kode dan memperbaiki import. Perbaikan bug dan perubahan perilaku dicatat di bagian "Temuan" di bawah, lalu dikerjakan setelah v0.2.0.
- **Langkah kecil, satu commit per langkah.** Setiap commit harus bisa dijalankan dan lulus tes. Kalau tes gagal, kembali ke commit sebelumnya, jangan menambal ke depan.
- **Freeze fitur selama refactor.** Kalau ada perbaikan mendesak untuk laptop akuisisi, kerjakan di `main` (monolith), beri tag `v0.1.x`, lalu porting ke branch refactor.
- Satu branch untuk seluruh refactor: `refactor/v0.2.0`, bercabang dari tag `v0.1.0`. Branch lama (`refactor/sync-modular`, `refactor/modularize-backend-frontend`) tidak di-merge.
- File sementara (log, salinan data uji, keluaran) disimpan di `tmp/` di root proyek. Folder ini sudah di-gitignore.

## 3. Fase

### Fase 0: Bekukan baseline
1. Commit pekerjaan di `feature/gate-fokus-tile`, lalu merge ke `main` (termasuk commit panduan pengguna `216ec2d`).
2. Tag `v0.1.0` di `main`: `git tag -a v0.1.0 -m "Baseline sebelum refactor"`.
3. Siapkan data uji di `tmp/data-uji/`: beberapa gambar capture asli, `capture_log.csv` format lama dan baru, JSON detail, dan `segmentation_log.csv`.
4. Tulis tes karakterisasi (lihat `04-rencana-uji.md`, bagian 2) di atas v0.1.0, lalu pastikan lulus. **Tes ini wajib ada sebelum Fase 1.**
5. Rekam acuan (`RECORD_EXPECTED=1`) ke `tests/expected_v0.1.0.json`, termasuk snapshot daftar route. Status (2026-11-23): selesai. Data uji asli disalin ke `tmp/data-uji/` (lihat `04-rencana-uji.md`), acuannya di `tmp/data-uji/expected.json`.

### Fase 1: Backend
Urutannya dari bagian yang paling sedikit bergantung ke yang paling banyak. Setelah tiap langkah: jalankan tes, lalu commit.

| Langkah | Pindahkan ke | Isi |
|---|---|---|
| 1.1 | `config.py` | Konstanta dan env var |
| 1.2 | `csvlog.py` | `_ensure_log_columns`, `save_lock`, `segmentation_log_lock` |
| 1.3 | `quality.py` | Fokus tile, `FocusTracker`, `ClipQuality`, `is_blank_frame` |
| 1.4 | `segmentation/export.py` | Export Excel dan COCO, beserta route-nya ke blueprint |
| 1.5 | `segmentation/storage.py`, `mock_model.py`, `routes.py` | Sisa segmentasi sebagai `segmentation_bp` |
| 1.6 | `camera.py` | ToupCam, `CameraManager`, `gen_mjpeg` |
| 1.7 | `capture.py` | Route kamera, capture, dan save sebagai blueprint |

Kamera dipindah paling akhir karena paling sulit diuji otomatis dan butuh hardware. Setelah langkah 1.6 dan 1.7, jalankan checklist manual kamera.

### Fase 2 dan 3: dipindah ke v0.3.0
Tidak dikerjakan di v0.2.0. Rencana lama di bawah hanya sebagai catatan; struktur frontend v0.3.0 diputuskan saat rombak UI.

#### (Dipindah) Frontend JS
1. Potong `app.js` menjadi 8 script klasik sesuai `02-arsitektur.md` 2.2, satu file per commit, dari atas ke bawah. Tiap commit menambah satu `<script defer>` di `index.html`.
2. Setelah tiap potongan: reload browser, pastikan Console bersih dari error, lalu jalankan checklist singkat untuk tab yang terkena.
3. Hapus `app.js` kalau isinya sudah kosong.

#### (Dipindah) CSS
Potong `style.css` menjadi 4 file dengan urutan blok tetap. Bandingkan tampilan kedua tab sebelum dan sesudah dengan screenshot di `tmp/screenshot/`.

### Fase 4: Rilis
1. Jalankan checklist manual lengkap di laptop pengembangan. Frontend tidak berubah, jadi fokusnya pada perilaku API, kamera, dan simpan/muat data.
2. Jalankan checklist manual lengkap di **laptop akuisisi** dengan kamera asli dan data lama.
3. Update `README.md` (bagian struktur kode), `CHANGELOG.md`, dan memory proyek.
4. Merge ke `main`, tag `v0.2.0`, lalu hapus branch refactor lama.

## 4. Risiko dan mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Instance global (kamera, tracker, lock) terduplikasi saat dipecah | Kamera dibuka dua kali, race condition saat save | Buat instance sekali di modulnya. Tes: `id()` sama dari dua modul (tes 2.5) |
| Import melingkar antar modul | App gagal start | Arah import satu arah: `config` -> `csvlog`/`quality`/`camera` -> blueprint -> `app` |
| Urutan script atau CSS berubah | Fungsi belum terdefinisi, tampilan bergeser | Urutan tag mengikuti urutan potongan asli, dan Console harus bersih |
| Format CSV/JSON berubah tanpa sadar | Data lama di lab tidak terbaca | Tes golden file terhadap data uji (tes 2.3, 2.4) |
| Regresi kamera di platform yang tidak diuji | Akuisisi di lab terhenti | Checklist manual per platform. Laptop akuisisi baru diupdate setelah lulus |
| Refactor berlarut, `main` terus berubah | Konflik merge seperti branch lama | Freeze fitur, kerjakan per fase, dan merge segera setelah Fase 4 |

## 5. Rollback di laptop akuisisi

```
git fetch --tags
git checkout v0.1.0        # kembali ke monolith
run.bat                    # atau ./run.sh
```

Data di folder akuisisi tidak ikut terpengaruh, karena refactor tidak mengubah format file.

## 6. Temuan (dikerjakan setelah v0.2.0)

Catat di sini bug atau ide yang ditemukan selama refactor, jangan langsung diperbaiki.

- `doCapture` langsung mengganti citra aktif, dan server menimpa `captured_frame` tanpa peringatan. Spasi yang tertekan tidak sengaja sebelum Simpan membuat citra hilang tanpa jejak (K-A3). Ditemukan di skenario lama.
- `fetch` di `doCapture`/`doSave` tidak dibungkus `try/catch`. Kalau server mati, UI diam tanpa pesan (K-C5).
- `/api/save` hanya mengembalikan "Gagal menyimpan file." tanpa penyebab, karena `cv2.imwrite` tidak memberi alasan (K-C2).
- Penghitung "Jumlah gambar tercapture" menampilkan nomor iterasi terakhir dari file, bukan jumlah sesi (K-A5).
