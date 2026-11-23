# Rencana UI v0.3.0

Status: dikerjakan di branch `feat/ui-v0.3.0` (dibuat dari `refactor/v0.2.0`, 2026-11-23).

## 1. Cakupan

- **Hanya frontend**: `templates/`, `static/`. Kontrak backend v0.2.0 tidak berubah (29 route, bentuk JSON sama).
- Acuan: prototipe Artifact (sumber `tmp/ui-prototipe/`) dan `01-brief-ux.md`.
- Dua layar dari prototipe yang fiturnya sudah ada: **Akuisisi** (model manual) dan **Analisis sel**. Pindah layar lewat navigasi tahap di header (tanpa reload, state tetap).
- Semua fitur v0.1.0 tetap ada (inventaris di bagian 3).

Tidak dikerjakan di v0.3.0 karena butuh backend baru (urutan menyusul, lihat `docs/use-case.md`):
- layar Sesi pasien, Laporan pasien, Penilaian citra, Akuisisi otomatis (Pindai);
- capture otomatis (UC-13), beberapa citra belum tersimpan sekaligus (K-A3), sisa penyimpanan, perkiraan jumlah eritrosit per pasien;
- mode label "Ukuran, bentuk, warna" (butuh field `attributes`, lihat `use-case.md` bagian 7);
- login/nama pengguna di header.

Temuan bug di `docs/refactor/03-rencana-refactor.md` bagian 6 juga belum dikerjakan di sini.

## 2. Struktur file

| File | Isi |
|---|---|
| `templates/index.html` | Kerangka dua layar, dialog Laporan dan Pengaturan model |
| `static/css/style.css` | Token warna (terang/gelap), komponen, tata letak |
| `static/fonts/` | Atkinson Hyperlegible (OFL), tanpa CDN |
| `static/js/common.js` | Elemen bersama: toast, modal pilihan, tema, pindah layar |
| `static/js/capture.js` | Layar Akuisisi: kamera, fokus, capture, simpan, riwayat |
| `static/js/segmentation.js` | Layar Analisis: segmentasi, koreksi, inspektur sel, export, model |
| `static/js/main.js` | Pendaftaran event dan inisialisasi |

Script klasik tanpa build step; urutan muat = urutan tabel. Logika dari `app.js` dipindah apa adanya, perubahan hanya di bagian yang tata letaknya berubah.

## 3. Inventaris fitur v0.1.0 dan tempatnya di v0.3.0

**Akuisisi**

| Fitur | Tempat baru |
|---|---|
| Pilih kamera, muat ulang daftar, resolusi, Hubungkan, Pengaturan driver (Windows) | Toolbar di atas stream, kelompok "Kamera" |
| Inisial pasien, pilih lokasi simpan, path folder | Bar sesi, dengan tanda prasyarat (kamera, ID, folder) |
| Ringkasan folder | Tombol di bar sesi, panel melayang |
| Stream MJPEG | Tengah, mengisi area kerja |
| Status fokus live, peta tile, reset puncak, toggle live, detail Tenengrad, peringatan pinggir, status CLIP | Chip status di atas stream (K-B2) dan panel kanan |
| Capture (Spasi), hasil capture, lencana fokus/kosong/pinggir/CLIP/tersimpan | Panel kanan, kartu "Hasil ambil" |
| Simpan (Enter), tiga konfirmasi (ID berubah, sudah tersimpan, buram) | Panel kanan; alasan tombol mati ditulis (K-A4) |
| Kirim ke Segmentasi | Panel kanan, "Kirim ke analisis" |
| Riwayat tersimpan + preview (panah, Esc, zoom) | Strip di bawah |
| Penghitung, format nama file | Strip bawah |

**Analisis**

| Fitur | Tempat baru |
|---|---|
| Inisial pasien, path gambar | Bar sesi |
| Pilih gambar, Muat hasil tersimpan, Proses batch, Jalankan, Simpan hasil | Bar sesi, dikelompokkan: Sumber, Model, Hasil |
| Gambar sumber / hasil segmentasi, zoom, pan | Tengah, toolbar di atasnya |
| Tambah sel, ukuran sel, nomor sel | Toolbar gambar, kelompok "Alat" dan "Tampilan" |
| Daftar sel, verdict, koreksi kelas, hapus, pilih massal, Tandai sisanya benar | Panel kanan, ditambah **inspektur sel** (tombol kelas besar untuk layar sentuh) |
| Shortcut 0-9, Delete, panah, +/- | Tetap; tambahan B (Benar) dan S (Salah). Verdict dari inspektur atau B/S langsung memilih sel berikutnya; "Tandai sisanya benar" juga ada di inspektur |
| Hasil di folder + filter | Panel kiri, "Antrean citra" |
| Ringkasan per kelas, tabel/grafik, sorot kelas | Panel kiri bawah |
| Ringkasan per pasien, Export Excel, Export COCO | Dialog "Laporan dan export" |
| Status model, path, ambang confidence | Dialog "Pengaturan model"; status model juga di banner dan bar status |

## 4. Uji

- Tes backend (`unittest`) tetap lulus; tidak ada file backend yang berubah.
- `node --check` untuk semua file JS.
- Smoke test di browser dengan webcam: setiap baris inventaris di atas dicoba sekali, tema terang/gelap, 1280x800 dan 1920x1080 tanpa scroll halaman.
- Belum bisa diuji di sini: MiiCam, layar sentuh Jetson.
