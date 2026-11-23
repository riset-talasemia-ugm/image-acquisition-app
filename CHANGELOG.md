# Changelog

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/) dan penomoran [SemVer](https://semver.org/lang/id/).

## [Unreleased]

Target rilis 0.2.0: refactor backend tanpa mengubah perilaku (lihat `docs/refactor/`). Frontend tidak berubah; ditulis ulang di 0.3.0.

### Changed
- `app.py` (2.383 baris) dipecah menjadi `config.py`, `csvlog.py`, `quality.py`, `camera.py`, `capture.py` (blueprint `capture_bp`), `utils.py`, dan paket `segmentation/` (blueprint `segmentation_bp`: `mock_model.py`, `storage.py`, `routes.py`, `export.py`). `app.py` tinggal 42 baris.
- Kode dipindah apa adanya: 90 definisi top-level v0.1.0 ada dengan teks identik, 29 route dengan URL, method, dan fungsi yang sama.

### Changed (UI, branch `feat/ui-v0.3.0`, target 0.3.0)
- Tampilan ditulis ulang mengikuti prototipe (`docs/ui/`): dua layar (Akuisisi, Analisis sel) dengan navigasi tahap, bar sesi, bar status, tema terang/gelap, font Atkinson Hyperlegible offline, tanpa scroll halaman.
- Akuisisi: setelah Ambil citra, area stream terbelah (live di kiri, citra diam sama besar di kanan beserta lencana fokus) selama citra belum disimpan, lalu live kembali penuh (K-B4; menggantikan thumbnail kecil di panel kanan). Status fokus juga tampil di atas stream, tanda prasyarat (kamera, inisial, folder), alasan tombol Simpan mati ditulis.
- Analisis: inspektur sel dengan tombol kelas dan verdict besar untuk layar sentuh, shortcut B (Benar) dan S (Salah) yang langsung pindah ke sel berikutnya, tombol "Tandai sisanya benar" juga di inspektur (alur v0.1.0: tandai yang salah, sisanya disetujui sekaligus), banner "alat bantu, bukan diagnosis" dan status model mock yang mencolok. Laporan/export dan pengaturan model pindah ke dialog.
- Galat: bar galat persisten (judul "Gagal", tidak hilang sendiri) dengan tombol pemulihan (Coba hubungkan lagi, Sambungkan ulang kamera, Pilih lokasi lain, Coba simpan lagi). Server mati tampil sebagai "Terputus dari aplikasi" dan hilang sendiri saat tersambung lagi; tombol tidak macet dalam keadaan mati.
- Ambil citra saat citra sebelumnya belum disimpan kini bertanya dulu (Simpan dulu, Buang, Batal).
- Penghitung "Tersimpan sesi ini" menghitung citra sesi, terpisah dari nomor iterasi.
- `/api/save` menyebut penyebab gagal (folder hilang, disk penuh, izin, gagal tulis) dalam field `code` dan `message`, dan menulis PNG lewat `cv2.imencode` sehingga path non-ASCII di Windows tidak gagal diam-diam.
- `/api/camera/status` menambah field `frozen` (stream beku: isi frame tidak berubah lebih dari 5 detik); UI menampilkan peringatan dengan tombol sambung ulang.
- Tes baru `tests/test_galat.py` (7 tes).

### Fixed (target 0.3.0)
- Menyimpan review dokter yang hanya menambah verdict (tanpa mengubah kelas) dianggap "duplikat" dan bisa batal tersimpan bila pengguna menekan Batal. Cek duplikat kini membandingkan isi deteksi lengkap dengan file tersimpan terakhir (ada sejak v0.1.0).
- Spasi saat modal konfirmasi terbuka menekan tombol yang disorot (mis. "tetap simpan" citra buram). Kini Spasi diabaikan di modal, Enter memilih (juga setelah klik di luar kotak), Esc membatalkan.
- "Kirim ke analisis" tetap aktif setelah capture baru yang belum disimpan dan mengirim citra lama. Kini dimatikan sampai citra baru disimpan.
- Grafik jumlah per kelas tidak terbaca di panel sempit (SVG 820 px diperkecil). Diganti batang horizontal dengan label dan angka biasa.

### Added (target 0.3.0)
- Capture otomatis tingkat 1 (UC-13): setelan di toolbar Akuisisi (default mati). Aplikasi memotret dan menyimpan sendiri saat frame lolos gerbang berurutan: ada sel, meja diam, lapang baru (bukan duplikat citra tersimpan terakhir), fokus di puncak dan baik. Daftar gerbang tampil di atas stream; citra otomatis ditandai "O" di riwayat. CLIP mode bayangan (dicatat, tidak memblokir). Ambang di `config.py` (`AUTO_*`), masih heuristik.
- Kolom `capture_mode` di `capture_log.csv` (`manual` / `otomatis-1`), dengan migrasi otomatis log lama. Daftar kolom di `tests/test_v010.py` ikut ditambah (perubahan format yang disengaja, bukan perekaman ulang snapshot).
- Tes `tests/test_autocapture.py` (7 tes).
- Cek perangkat saat menyala (F5): dialog sekali per nyala server berisi jam (ditandai bila tahunnya mustahil), jumlah kamera, dan sisa penyimpanan, dengan petunjuk mengatur jam.
- Penjaga penyimpanan (F11): sisa ruang folder simpan di bar status, peringatan di bawah 2 GB.
- Sesi pasien (UC-01): inisial, folder, resolusi, dan kamera diingat dan dipulihkan saat halaman dibuka lagi; bar sesi menyebut jumlah citra pasien itu yang sudah ada di folder.
- Pemulihan (UC-10): citra yang belum disimpan disalin ke `recovery/` dan ditawarkan untuk dipulihkan setelah aplikasi tertutup; draf koreksi segmentasi yang belum disimpan juga ditawarkan untuk dilanjutkan.
- Lembar penilaian citra oleh dokter (F14): layar 2 "Penilaian citra" (urutan kerja kini Akuisisi, Penilaian citra, Analisis sel). Citra tampil penuh dengan ID acak, tanpa nama file dan skor; Layak/Tidak layak (L/T), alasan wajib bila tidak layak (1-6), catatan opsional, Sebelumnya. Hasil di `penilaian_citra.csv`, peta ID di `penilaian_citra_id.json` (folder citra). Modul `rating.py`.
- "Proses satu folder" melewati citra yang dinilai tidak layak oleh salah satu penilai; konfirmasi menyebut jumlah tidak layak dan yang belum dinilai.
- Persiapan model multi-label (ukuran, bentuk, warna; eksperimen `../sardjito-atribut-eksperimen`): field opsional `attributes` per deteksi dengan kosakata yang sama dengan eksperimen, kelas turunan lewat `resolve_class` yang disalin dari repo dataset (`attributes.py`), pilihan "Jenis keluaran model" (kelas tunggal / atribut) di Pengaturan model (mock ikut mengeluarkan atribut), dan mode review "Ukuran, bentuk, warna" di inspektur sel (koreksi dokter di `correctedAttributes`, kelas turunannya menjadi kelas koreksi). Mode label tersimpan per hasil (`labelMode`, hanya ditulis untuk mode atribut sehingga file v0.1.0 tidak berubah). Tes `tests/test_atribut.py`.
- Laporan pasien siap cetak/PDF (UC-07): tombol di dialog Laporan dan export membuka halaman A4 (`/laporan`, `report.py`) berisi pasien dan pemeriksaan, kualitas data, hasil morfologi sesudah review (eritrosit tanpa Uncategorised, tanda bila kurang dari 1.000), contoh citra, kesimpulan dokter (diisi di halaman), pernyataan alat bantu, dan tanda tangan. Peringatan mencolok selama model masih mock. Tanpa nama file/path. PDF lewat Cetak > Simpan sebagai PDF.
- Peta fokus di atas stream (Tampilan > Peta fokus), semi-transparan, mengikuti posisi gambar.
- Inspektur sel menampilkan potongan sel terpilih yang diperbesar dengan garis tepi berwarna kelas.
- Rute baru `/api/system/status`, `/api/recovery/capture`, `/api/segmentation/open-path`. Tes rute kini menerima rute tambahan yang tercatat eksplisit; rute v0.1.0 tetap dibandingkan dengan snapshot.
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
