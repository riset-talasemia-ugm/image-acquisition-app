# Rencana Uji Refactor

Ada dua lapis pengujian:
1. **Tes otomatis (karakterisasi)**: mengunci perilaku v0.1.0 sebelum refactor dimulai, lalu dijalankan di setiap commit.
2. **Checklist manual**: untuk hal yang tidak bisa diuji otomatis, seperti kamera asli, dialog native, dan tampilan.

## 1. Lingkungan dan lokasi file

- Tes ditulis dengan `unittest` bawaan Python dan `app.test_client()` Flask, tanpa dependency baru.
- File tes: `tests/test_v010.py`. Jalankan dengan: `python -m unittest discover -s tests -v` (~3 detik).
- Nilai acuan v0.1.0 ada di `tests/expected_v0.1.0.json`, direkam sekali di tag `v0.1.0` dengan `RECORD_EXPECTED=1`. Selama refactor file ini **tidak boleh direkam ulang**. Kalau ada tes yang gagal, yang diperbaiki kodenya, bukan acuannya.
- Sebelum dibandingkan, path folder uji dan timestamp di respons API diganti placeholder (`<DIR>`, `<TS>`).
- **Semua keluaran tes ditulis ke `tmp/test-run/`** di root proyek, bukan ke folder temp sistem di drive C. Tiap tes membuat subfolder sendiri lalu menghapusnya sesudah selesai.
- Gambar uji dibuat sintetis dan deterministik di dalam tes, jadi tidak ada file fixture biner.
- **Gambar pasien asli tidak di-commit.** Simpan di `tmp/data-uji/`. Tes yang memakainya otomatis di-skip kalau folder itu tidak ada.

## 2. Tes otomatis

Ditulis di Fase 0, terhadap v0.1.0. Tes ini **tidak boleh diubah** selama refactor, kecuali import-nya.

| No | Tes | Yang dicek | Kontrak |
|---|---|---|---|
| 2.1 | Snapshot route | Daftar `(rule, methods)` dari `app.url_map` sama dengan acuan | 01 §4.1 |
| 2.2 | Helper murni | `safe_slug`, `next_iteration_from_folder` (folder kosong, lanjut nomor, slug beda), `resize_for_save`, `is_blank_frame` (frame hitam vs berisi) | F-CAP-1, F-CAP-6 |
| 2.3 | Migrasi CSV | `_ensure_log_columns` pada CSV kolom lama: baris lama tetap ada, kolom baru kosong, urutan header sesuai 01 §4.2 | 01 §4.2 |
| 2.4 | Simpan dan muat segmentasi | `random.seed` tetap, lalu `POST run`, `POST save` ke `tmp/test-run/`. Isi JSON detail dan baris CSV sesuai format. `load-path` mengembalikan deteksi yang sama. Save kedua tanpa perubahan memberi tanda duplikat | F-SEG-2, F-SEG-5, F-SEG-6 |
| 2.5 | Instance tunggal | Objek kamera, tracker fokus, dan kedua lock yang di-import dari modul berbeda punya `id()` yang sama. **Ditambahkan di Fase 1**, karena di v0.1.0 semuanya masih satu modul | NF-4 |
| 2.6 | Fokus deterministik | `analyze_focus` pada gambar fixture menghasilkan angka sama dengan nilai yang direkam di v0.1.0 (toleransi 1e-6) | F-CAP-2 |
| 2.7 | Export | `export-report` menghasilkan xlsx yang bisa dibuka openpyxl dengan header yang benar. `export-coco` menghasilkan `images`/`annotations`/`categories` dengan 13 kategori sesuai urutan `RBC_CLASS_LABELS` | F-SEG-9 |
| 2.8 | Ringkasan | `folder-summary` dan `patient-summary` pada folder fixture memberi jumlah per pasien dan per kelas yang benar | F-CAP-8, F-SEG-8 |
| 2.9 | Data lama (opsional) | Bila `tmp/data-uji/` ada: `list-results` dan `patient-summary` pada data akuisisi asli tidak error, dan hasilnya sama dengan v0.1.0 | 01 §4.2 |

Acuan tes 2.9 berasal dari data pasien, jadi disimpan di `tmp/data-uji/expected.json` dan tidak di-commit. Rekam acuan ini dengan `RECORD_EXPECTED=1` sambil checkout `v0.1.0`, sebelum kode refactor menyentuh folder itu.

Yang tidak diuji otomatis: `CameraManager` dengan hardware, `/stream`, dialog tkinter (`select-folder`, `select-image`, `load`, `batch-select`), dan CLIP (model 600 MB).

## 3. Checklist manual

Isi tabel ini setiap selesai satu fase (✓ / ✗ + catatan). Simpan hasilnya di commit atau di `docs/logbook.md` kalau ada.

### 3.1 Start dan platform
- [ ] `run.bat` di Windows: venv dibuat/diupdate, browser terbuka, tanpa error di terminal.
- [ ] `run.sh` di Linux x86_64.
- [ ] Jetson: fallback ToupCam berjalan (kamera MiiCam).
- [ ] `run-clip.bat`: status pemuatan CLIP muncul di kartu fokus.
- [ ] Console browser (F12) bersih dari error di kedua tab.

### 3.2 Tab Capture (dengan kamera asli)
- [ ] Daftar kamera muncul, tombol refresh berfungsi.
- [ ] Hubungkan dengan "Bawaan kamera" dan satu resolusi lain, lalu cek resolusi aktual yang tampil.
- [ ] Stream berjalan. Cabut kamera: status berubah jadi terputus. Colok lagi lalu hubungkan ulang.
- [ ] Reload halaman saat kamera aktif: status pulih tanpa connect ulang.
- [ ] Dialog setelan kamera terbuka.
- [ ] Kartu fokus: "Puncak belum terkonfirmasi", lalu putar fokus melewati puncak sampai muncul Baik/Sedang/Buram. Peta tile berwarna, Reset puncak berfungsi, centang Live bisa dimatikan.
- [ ] Ganti lapang pandang: puncak tereset otomatis.
- [ ] Capture: badge fokus, pinggir lemah, dan frame kosong muncul sesuai kondisi.
- [ ] Pilih folder: Ringkasan Folder muncul.
- [ ] Save: nama file dan nomor iterasi benar, baris `capture_log.csv` lengkap, ringkasan terupdate.
- [ ] Save saat Buram meminta konfirmasi.
- [ ] Galeri: preview, zoom 100%, panah kiri/kanan, Esc.
- [ ] Spasi = Capture, Enter = Save. Keduanya tidak aktif saat preview atau modal terbuka.

### 3.3 Tab Segmentasi
- [ ] Kirim dari Capture, dan pilih gambar lewat dialog: ID pasien terisi otomatis.
- [ ] Jalankan: overlay, nomor sel, total sel, legenda, tabel dan grafik kelas.
- [ ] Zoom/pan, klik sel, highlight per kelas, ambang confidence.
- [ ] Ubah kelas, tambah sel manual, hapus, resize, koreksi massal, verdict Benar/Salah, "Tandai Sisanya Benar", dan statistik verdict.
- [ ] Shortcut keyboard koreksi sel.
- [ ] Simpan: JSON dan CSV terbentuk. Simpan lagi tanpa perubahan memunculkan konfirmasi duplikat.
- [ ] Muat hasil (dialog dan dari daftar hasil folder), filter daftar.
- [ ] Batch satu folder.
- [ ] Ringkasan per pasien, export Excel (buka di Excel), export COCO.
- [ ] Status model dan simpan konfigurasi path model.

### 3.4 Kompatibilitas data
- [ ] Buka folder data akuisisi dari v0.1.0 (salinan di `tmp/data-uji/`, **bukan folder asli**): ringkasan, daftar hasil, dan muat hasil normal.
- [ ] `capture_log.csv` format lama termigrasi benar setelah satu Save.

## 4. Kapan dijalankan

| Saat | Tes otomatis | Checklist manual |
|---|---|---|
| Setiap commit refactor | Semua | Tidak |
| Selesai langkah 1.6/1.7 (kamera) | Semua | 3.1 (Windows) + 3.2 |
| Selesai tiap potongan JS/CSS | Semua | Bagian tab yang terkena + Console |
| Sebelum merge v0.2.0 | Semua | Lengkap, di laptop pengembangan **dan** laptop akuisisi |
