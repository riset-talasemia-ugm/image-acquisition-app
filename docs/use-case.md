# Use Case

Status per 2026-11-23. Kolom **Status**:
- **Ada**: sudah ada di v0.1.0.
- **Baru**: dikonfirmasi pengguna, belum ada.
- **Direncanakan**: disiapkan desain dan dokumennya, dikerjakan belakangan.
- **Usulan**: belum dikonfirmasi.

## 1. Konteks

- **Tujuan utama produk** (dikonfirmasi): versi ringkas dan murah dari alat morfologi darah otomatis, yang biasanya mahal, untuk daerah 3T. Intinya **capture otomatis** (UC-13).
- **Tujuan pemakaian** (dikonfirmasi): **dua sekaligus**, yaitu (a) mengambil data citra untuk melatih model, dan (b) skrining talasemia di unit kesehatan daerah 3T.
- **Perangkat**: Jetson Orin Nano + mikroskop cahaya + kamera USB. Layar sentuh atau monitor biasa. Laptop untuk pengembangan dan riset.
- **Dokter**: ada di lokasi. Review jarak jauh tetap disiapkan (UC-05).
- **Identitas pasien**: untuk sementara cukup ID pasien. Integrasi rekam medis dan kebijakan persetujuan/privasi dibahas nanti (lihat `operasional.md`).

## 2. Aktor

| Aktor | Peran |
|---|---|
| Laboran/operator | Menyiapkan sesi, mengambil citra, menjalankan analisis |
| Dokter di lokasi | Mereview dan mengoreksi sel, menulis kesimpulan skrining, menandatangani laporan |
| Dokter jarak jauh | Mereview dari perangkat lain bila dokter tidak di lokasi |
| Peneliti | Batch, statistik, export dataset, pengaturan model |
| Mahasiswa | Belajar morfologi sel, membantu anotasi di bawah supervisi |
| Pengelola perangkat | Instalasi, pembaruan, cadangan data (lihat `operasional.md`) |

## 3. Daftar use case

| ID | Use case | Aktor | Status | Kebutuhan dasar di v0.1.0 |
|---|---|---|---|---|
| UC-01 | Mulai atau lanjutkan sesi pasien | Laboran | Ada (sebagian) | F-CAP-5, F-CAP-8 |
| UC-02 | Ambil citra berkualitas | Laboran | Ada | F-CAM-*, F-CAP-1..9 |
| UC-03 | Analisis sel otomatis | Laboran, dokter | Ada (model mock) | F-SEG-2, F-SEG-7 |
| UC-04 | Review dan koreksi sel | Dokter di lokasi | Ada | F-SEG-3..6 |
| UC-05 | Review jarak jauh | Dokter jarak jauh | Direncanakan | - |
| UC-06 | Hasil skrining per pasien | Dokter | Baru | F-SEG-8 (sebagian) |
| UC-07 | Laporan pasien untuk arsip dan rujukan | Dokter, laboran | Baru | - |
| UC-08 | Statistik dan laporan Excel | Peneliti | Ada, diperluas | F-SEG-9 |
| UC-09 | Export dataset pelatihan | Peneliti | Ada | F-SEG-9 (COCO) |
| UC-10 | Pulih setelah listrik padam atau aplikasi tertutup | Semua | Baru | - |
| UC-11 | Belajar morfologi sel | Mahasiswa | Usulan | - |
| UC-12 | Kelola perangkat dan data | Pengelola perangkat | Direncanakan | lihat `operasional.md` |
| **UC-13** | **Capture otomatis** | Laboran | **Baru, prioritas utama** | `FocusTracker` (deteksi ganti lapang, puncak fokus) |

## 4. Rincian

### UC-01 Mulai atau lanjutkan sesi pasien
1. Laboran mengisi ID pasien. Folder simpan dipilih sekali per hari/lokasi dan diingat.
2. Kalau ID pasien sudah punya citra di folder itu, aplikasi menampilkan jumlahnya dan menawarkan untuk melanjutkan.
3. Sesi memuat target jumlah citra per pasien (usulan, nilainya ditentukan tim klinis).

### UC-02 Ambil citra berkualitas
Alurnya sama seperti v0.1.0: hubungkan kamera, cari puncak fokus, ambil citra, periksa badge kualitas, simpan. Citra buram tetap bisa disimpan setelah konfirmasi.

### UC-03 Analisis sel otomatis
Per citra atau batch satu pasien. Hasil model ditandai sebagai alat bantu. Selama model masih mock, statusnya tampil mencolok di semua layar.

### UC-04 Review dan koreksi sel
Dokter memeriksa sel per sel (pilih kelas, Benar/Salah, tambah/hapus/ubah ukuran sel), lalu menyimpan. Hasil review menjadi data pelatihan (UC-09) sekaligus dasar skrining (UC-06).

### UC-05 Review jarak jauh (direncanakan)
Internet di 3T terbatas, jadi rancangan awalnya tidak bergantung pada koneksi terus-menerus:
1. Laboran membuat **paket review** per pasien: citra, hasil analisis, dan metadata dalam satu file (mis. `.zip`).
2. Paket dikirim lewat flashdisk atau diunggah saat ada sinyal.
3. Dokter membuka paket di aplikasi yang sama (laptop atau perangkat lain), mereview, lalu mengekspor **paket hasil review**.
4. Paket hasil diimpor kembali di Jetson dan menggabungkan verdict serta koreksi tanpa menimpa data asli. Konflik (dua review untuk citra yang sama) ditampilkan.

Yang perlu diputuskan nanti: media kirim, enkripsi paket, dan siapa yang berwenang menyetujui hasil.

### UC-06 Hasil skrining per pasien (baru)
1. Setelah semua citra pasien direview, aplikasi menampilkan ringkasan: jumlah citra, total sel, persentase per kelas morfologi, dan statistik review dokter.
2. Dokter menulis **kesimpulan skrining** dan **rekomendasi** (mis. dirujuk untuk pemeriksaan lanjutan).
3. Kalau jumlah eritrosit sesudah review di bawah 1.000, layar dan laporan menampilkan peringatan beserta perkiraan jumlah citra yang masih dibutuhkan. **Laporan tetap boleh dikunci dengan catatan** (dikonfirmasi 2026-11-23): dokter wajib menulis alasannya, dan catatan itu tercetak di laporan PDF di samping jumlah selnya.
4. **Aplikasi tidak menghasilkan diagnosis sendiri.** Kalau nanti ada indikasi otomatis (mis. ambang persentase sel target/mikrosit), kriterianya wajib berasal dari tim klinis, dicatat beserta sumbernya, dan ditampilkan sebagai saran.

### UC-07 Laporan pasien (baru)
Lihat bagian 5 untuk isi dan format.

### UC-08 Statistik dan laporan Excel
Export Excel yang ada (Ringkasan Pasien, Detail per Gambar, Detail per Sel) diperluas dengan statistik lintas pasien dan rentang tanggal.

### UC-09 Export dataset pelatihan
COCO seperti v0.1.0, dengan opsi hanya sel yang sudah direview.

### UC-10 Pulih setelah listrik padam (baru)
Sesi aktif (ID pasien, folder, citra terakhir yang belum disimpan, koreksi yang belum disimpan) dicatat ke disk secara berkala. Saat aplikasi dibuka lagi, pengguna ditawari untuk melanjutkan.

### UC-11 Belajar morfologi sel (usulan)
Contoh tiap kelas sel dari data yang sudah direview dokter, dengan penjelasan singkat. Perlu persetujuan penggunaan data.

### UC-13 Capture otomatis (baru, prioritas utama)
**Dua model perangkat** (dikonfirmasi 2026-11-23). Aplikasinya satu, dan layar Akuisisi menyesuaikan perangkat yang terpasang:
- **Model manual**: mikroskop tanpa motor. Operator menggeser meja dan memutar fokus. Capture lewat tombol (Spasi), dan ada **setelan "Capture otomatis"** (default mati). Kalau dinyalakan, aplikasi memotret dan menyimpan sendiri saat lapang lolos gerbang (tingkat 1 di bawah).
- **Model otomatis**: meja XY dan fokus bermotor dari tim hardware (tingkat 2-3). Operator memasang preparat, lalu aplikasi memindai, mencari fokus, dan memotret sendiri sampai target tercapai. Capture manual tetap bisa dipakai saat pemindaian dijeda.

Alat morfologi otomatis yang mahal menggerakkan meja preparat dan fokus dengan motor, lalu memotret banyak lapang pandang tanpa operator. Versi ringkasnya disusun bertingkat, supaya tingkat 1 sudah berguna tanpa perangkat keras tambahan:

| Tingkat | Perangkat keras | Yang otomatis | Peran operator |
|---|---|---|---|
| 1. Capture otomatis berbantuan | Tidak ada tambahan | Aplikasi memotret dan menyimpan sendiri saat lapang pandang baru sudah diam, fokus di puncak dan berstatus baik, bukan duplikat (fitur 4), dan kepadatan sel layak | Menggeser meja dan memutar fokus |
| 2. Fokus otomatis | Motor pada knop fokus halus (atau motor fokus kamera, bila ada, lihat `ToupcamFocusMotor` di SDK) | Mencari puncak fokus per lapang | Menggeser meja |
| 3. Pemindaian penuh | Meja XY bermotor + motor fokus (mis. rancangan terbuka seperti OpenFlexure) | Mencari zona baca, memindai lapang berurutan, fokus per lapang, berhenti saat target sel tercapai (mis. 1000 eritrosit) | Memasang preparat |

**Gerbang tingkat 1** (dikonfirmasi 2026-11-23: CLIP menilai apakah lapang pandang bagus). Urutannya dari yang murah ke yang mahal, berhenti di kegagalan pertama:
1. Frame tidak kosong (`is_blank_frame`).
2. Lapang pandang baru dan meja sudah diam: tidak ada gerakan selama beberapa frame, dan tidak sama dengan citra tersimpan sebelumnya (F4).
3. Fokus: puncak terkonfirmasi dan status baik (Tenengrad per tile seluruh frame, sudah ada di v0.1.0).
4. Semantik CLIP: skor `kepadatan`/`gabungan_v2` di atas ambang.

**Status CLIP dari eksperimen** (`akuisisi-otomatis/eksperimen-clip.md`):
- CLIP tidak dipakai untuk menilai fokus.
- Skor semantiknya terutama mengukur kepadatan sel.
- Prompt `monolayer` terbalik arahnya, jadi tidak dipakai.
- **Ambang belum bisa ditetapkan karena belum ada label dokter.**
- Latensi di Orin Nano belum diukur.

Karena itu, gerbang 4 dijalankan dulu dalam **mode bayangan**: skornya dicatat tetapi tidak memblokir. Semua kandidat yang lolos gerbang 1-3 disimpan beserta skor CLIP-nya. Citra ini sekaligus menjadi bahan lembar penilaian dokter (layak atau tidak, beserta alasannya). Dari label itu ambang dikalibrasi (Youden's J, dipisah per pasien), dan baru setelahnya gerbang 4 dibuat memblokir.

Penilaian dokter tersedia (dikonfirmasi 2026-11-23). Lembar penilaian dibuat di dalam aplikasi (F14): citra penuh dengan ID acak, tanpa nama pasien dan tanpa skor, dengan pilihan layak atau tidak dan alasannya (buram, pinggir buram, overlap, kosong/jarang, artefak).

**Perangkat keras tingkat 2-3 dikerjakan tim hardware.** Tugas sisi software: abstraksi sumbu motor dengan simulasi (`FakeAxis`) supaya alur bisa diuji tanpa alat, dan dokumen antarmuka yang disepakati dengan tim hardware (perintah gerak, homing, limit, status, stop darurat).

Aturan untuk semua tingkat:
- **Target per pasien: minimal 1.000 eritrosit** (dikonfirmasi pengguna 2026-11-23). Jumlah citra mengikuti, biasanya sekitar 15-20 citra dengan kepadatan normal.
- **Jumlah resmi dihitung sesudah review dokter** (dikonfirmasi 2026-11-23), yaitu dari kelas akhir setelah koreksi, tambah, dan hapus sel.
- Selama akuisisi belum ada review, jadi progres "x dari 1.000" memakai **perkiraan** dari hasil model dan diberi label perkiraan. Capture otomatis dan pemindaian berhenti saat perkiraan mencapai target, ditambah cadangan kecil (mis. 10%) supaya jumlahnya tetap cukup kalau dokter menghapus sel. Besar cadangannya diputuskan setelah ada data review.
- Pada pemindaian bermotor dengan overlap antar lapang, sel di area overlap harus **dihitung satu kali**. Caranya: hanya sel yang titik pusatnya berada di area inti lapang (di luar pita overlap) yang dihitung, atau sel dicocokkan antar lapang memakai posisi meja.
- Tiap citra otomatis tetap lewat gerbang kualitas yang sama dengan capture manual, dan alasan citra ditolak dicatat (mis. buram, duplikat, terlalu padat).
- Capture manual tetap tersedia.
- Log mencatat apakah citra diambil otomatis atau manual, dan dengan tingkat berapa.

**Status tingkat 1 (2026-11-23, branch `feat/ui-v0.3.0`):** sudah dibuat sebagai setelan "Capture otomatis" (default mati) di toolbar layar Akuisisi.
- Gerbang di `autocapture.py`, dinilai pada poll `/api/focus/live?auto=1`: tidak kosong, meja diam (NCC citra kasar antar poll >= `AUTO_STILL_NCC` selama `AUTO_STILL_CHECKS` poll), lapang baru (NCC dengan citra tersimpan terakhir < `AUTO_DUPLICATE_NCC`), fokus terkonfirmasi dan "baik". Ambang di `config.py`, masih heuristik dan harus dikalibrasi di mikroskop asli.
- CLIP mode bayangan: skor dicatat saat simpan seperti capture manual, tidak memblokir.
- Log: kolom baru `capture_mode` di `capture_log.csv` (`manual` / `otomatis-1`), log lama dimigrasi otomatis.
- Belum: penghitung alasan penolakan per lapang, progres "x dari 1.000" (butuh perkiraan jumlah sel dari model asli), berhenti otomatis saat target tercapai.

**Rancangan yang sudah ada:** `akuisisi-otomatis/rancangan.md` berisi rancangan rinci tingkat 3:
- motor stepper yang dikendalikan langsung lewat GPIO Jetson, untuk sumbu Z dan meja XY berpola snake;
- state machine akuisisi, strategi autofokus, gerbang kualitas (kosong, Tenengrad, CLIP), dan enam tahapan pengerjaan.

Tahap 1 (metrik fokus Tenengrad per tile) sudah ada di v0.1.0. Tingkat 1 di tabel atas adalah tambahan yang bisa jalan sebelum motor tersedia. Pertanyaan terbuka di rancangan itu (GPIO langsung atau mikrokontroler, limit switch, travel Z, ketersediaan perangkat keras) belum dijawab.

## 5. Laporan dan dokumen keluaran

Format laporan v0.1.0 (Excel, 3 sheet) tetap menjadi dasar. Rekomendasi per jenis keluaran:

| Keluaran | Untuk | Format | Alasan |
|---|---|---|---|
| Laporan pasien | Arsip unit kesehatan, rujukan | **PDF** | Tidak mudah diubah, mudah dicetak, tampil sama di perangkat mana pun. Dibuat dari halaman HTML siap cetak di aplikasi (Cetak/Simpan PDF dari browser), sehingga tidak butuh dependency baru dan jalan offline di Jetson |
| Laporan pasien yang bisa diedit | Dokter yang ingin menambah catatan di luar aplikasi | DOCX (opsional) | Hanya kalau memang dibutuhkan. Butuh `python-docx`, dan dokumen bisa berubah setelah ditandatangani, jadi PDF tetap menjadi versi resmi |
| Statistik | Peneliti | **Excel** (sudah ada, diperluas) | Bisa langsung diolah |
| Dataset | Peneliti | COCO JSON (sudah ada) | Standar pelatihan model |
| Ringkasan riset | Peneliti | Markdown (opsional) | Cocok untuk logbook dan repo, tidak untuk unit kesehatan |

**Isi laporan pasien** (usulan, perlu disetujui tim klinis):
1. Kepala: nama unit kesehatan, tanggal pemeriksaan, ID pasien, nomor laporan.
2. Pemeriksaan: operator, dokter pemeriksa, perangkat dan versi aplikasi, versi model beserta statusnya.
3. Kualitas data: jumlah citra, jumlah yang fokusnya baik/sedang/buram.
4. Hasil morfologi: total sel, jumlah dan persentase per kelas, serta jumlah sel yang direview dan dikoreksi dokter.
5. Contoh citra: 2-4 potongan citra representatif.
6. Kesimpulan dan rekomendasi dokter (teks dari dokter, bukan dari model).
7. Pernyataan: "Hasil analisis otomatis adalah alat bantu. Kesimpulan ditetapkan oleh dokter pemeriksa."
8. Tanda tangan dokter dan tanggal.

**Perbandingan sistem dan dokter (F15, dikonfirmasi 2026-11-23).** Dibuat sesudah review dokter. **Satu file `.xlsx` berisi satu batch pasien**, dengan format yang sama seperti `label-asli.xlsx` di `tambahan-dataset/batch/<ID>/` (folder induk), supaya dokter langsung mengenalinya.

Sheet utama berisi satu blok kolom per gambar, berjajar ke kanan:

```
Baris 1:  <nama file gambar 1>                  | <nama file gambar 2> ...
Baris 2:  no. | Pendapat Saya | Pendapat Dokter | no. | Pendapat Saya | Pendapat Dokter
Baris 3+: 1   | Microcyte     | Microcyte       | 1   | ...
          2   | Normal cell   | Target cell     |
```

- **Nomor sel** sama dengan nomor di overlay hasil analisis, supaya setiap baris bisa dicocokkan ke selnya di gambar.
- **Pendapat Saya** = kelas dari sistem. **Pendapat Dokter** = kelas akhir sesudah review.
- **Keduanya berupa satu label** dari daftar kelas model, karena model hanya mengeluarkan satu label per sel (dikonfirmasi 2026-11-23). Ukuran, bentuk, dan warna tidak dipisah dulu, dan review dokter di aplikasi tetap memilih satu kelas.
- **Setelan mode label review** (dikonfirmasi 2026-11-23):
  - **Satu kelas** (default): dokter memilih satu kelas per sel, dan file berbentuk seperti contoh di atas.
  - **Ukuran, bentuk, warna** (opsional): dokter memilih tiga atribut, sama seperti kebiasaan di `label-asli.xlsx`. Kelas untuk dibandingkan dengan model diturunkan otomatis dengan aturan pemetaan dataset Sardjito (`tambahan-dataset`, bagian Pemetaan kelas; aturannya dipakai dari sana, tidak ditulis ulang). Di file perbandingan, Pendapat Dokter berisi tiga kolom (Ukuran, Bentuk, Warna) ditambah satu kolom kelas turunan, sedangkan Pendapat Saya tetap satu label. File mode ini cocok dengan format pipeline dataset.
  - Mode tersimpan di setiap hasil, supaya hasil dari kedua mode tidak tertukar saat diekspor.
- Sel yang dihapus dokter: Pendapat Dokter diisi "bukan sel / dihapus". Sel yang ditambah dokter: Pendapat Saya diisi "tidak terdeteksi".
- Format profesional: judul tebal, dua baris judul dibekukan, lebar kolom rapi, dan pemisah yang jelas antar blok gambar.

Sheet tambahan di file yang sama (dikonfirmasi 2026-11-23):

- **Ringkasan**: per pasien dan total batch; jumlah sel, jumlah setuju, persen kesepakatan, kappa, sel dihapus dokter, sel ditambah dokter, jumlah eritrosit (tanpa Uncategorised) sesudah review.
- **Matriks**: tabel silang kelas sistem (baris) dan kelas dokter (kolom), termasuk baris "ditambah dokter" dan kolom "dihapus dokter".

Sheet Per kelas (precision, recall, F1) belum dibuat; ditambah bila diperlukan untuk evaluasi model.

Catatan: tata letak blok mengikuti `label-asli.xlsx`, tetapi isinya satu label per kolom. Kalau nanti file ini mau dibaca pipeline dataset (`tambahan-dataset/skrip/rapikan_label.py`, yang mengharapkan Ukuran, Bentuk, dan Warna), pembacanya perlu disesuaikan di repo dataset.

Perubahan data yang dibutuhkan (dikerjakan setelah v0.2.0):
- **Sel yang dihapus dokter tidak dibuang**, tetapi ditandai `deletedByDoctor: true` di JSON detail. Sel itu disembunyikan di UI dan tidak dihitung, tetapi tetap tercatat sebagai deteksi salah model. Sekarang `deleteDetection` di `app.js` membuang sel dari daftar.
- **Sel tambahan dokter** (`manual: true`) diperlakukan sebagai terlewat oleh model, dan tidak dihitung sebagai prediksi `Uncategorised`. Sekarang kelas model sel manual diisi `Uncategorised` sebagai pengisi.
- Saat ukuran sel diubah, mask asli model disimpan (`originalMask`), supaya kualitas segmentasi juga bisa dibandingkan, bukan hanya kelasnya.
- Selama model masih mock, file ini hanya berguna untuk menguji alurnya. Angkanya belum bermakna.

**Profesional** di sini berarti: tata letak tetap dan rapi untuk cetak A4, tipografi sama dengan aplikasi, tabel bernomor, tidak ada data teknis yang tidak dipahami pembaca klinis (path, nama file internal), dan setiap angka bisa ditelusuri ke data sumbernya.

## 6. Fitur tambahan yang disetujui (2026-11-23)

| No | Fitur | Catatan |
|---|---|---|
| F1 | Jejak audit + login PIN per pengguna | **Opsional** |
| F2 | Data hematologi pendukung (Hb, MCV, MCH, RDW, RBC) + indeks Mentzer | **Kolom opsional**. Ambang interpretasi dari tim klinis |
| F3 | Metadata preparat + citra acuan warna | **Kolom opsional** |
| F4 | Deteksi lapang pandang ganda | Juga menjadi gerbang capture otomatis (UC-13) |
| F5 | Cek perangkat saat menyala, termasuk konfirmasi jam | Jetson tanpa baterai jam |
| F6 | Antrean review berdasarkan keraguan model | |
| F7 | Review ganda + kesepakatan antar dokter (kappa) | |
| F8 | Versi model di setiap hasil | |
| F9 | Rekap untuk program kesehatan | |
| F10 | Mode kiosk di Jetson + tombol matikan yang aman | |
| F11 | Penjaga ruang penyimpanan | |
| F12 | Panduan dan troubleshooting di dalam aplikasi | |
| F13 | Riwayat kunjungan pasien | |
| F14 | Lembar penilaian kualitas citra oleh dokter | Untuk kalibrasi gerbang CLIP (UC-13) |
| F15 | File Excel perbandingan sistem dan dokter | Dibuat sesudah review dokter, lihat bagian 5 |

Juga disetujui sebelumnya: review jarak jauh (UC-05), laporan pasien PDF (UC-07), statistik Excel (UC-08), dan pemulihan sesi (UC-10).

## 7. Daftar kelas morfologi (belum final)

Status per 2026-11-23: **daftar kelas final menunggu hasil eksperimen** di `../sardjito-rbc-eksperimen` (folder induk), apakah dataset Sardjito saja sudah cukup atau perlu digabung dengan Chula.

| ID | Kelas | Chula-RBC-12 (v0.1.0 saat ini) | Sardjito |
|---|---|---|---|
| 0 | Normal cell | ada | ada |
| 1 | Macrocyte | ada | ada |
| 2 | Microcyte | ada | ada |
| 3 | Spherocyte | ada | ada |
| 4 | Target cell | ada | ada |
| 5 | Stomatocyte | ada | ada |
| 6 | Ovalocyte | ada | ada |
| 7 | Teardrop | ada | ada |
| 8 | Burr cell | ada | ada |
| 9 | Schistocyte | ada | ada |
| 10 | Uncategorised | ada | ada |
| 11 | Hypochromia | ada | ada |
| 12 | Elliptocyte | ada | ada |
| 13 | Bite | - | ada |
| 14 | Blister | - | ada |
| 15 | Microcytic Hypochromia | - | ada |

Sumber: `dataset-publik/Chula-RBC-12-Dataset/README.md` dan `tambahan-dataset/README.md` (keduanya di folder induk). ID 0-12 sama di kedua dataset. Sel `Unlabeled` di mask Sardjito bukan kelas, dan ditimpa warna latar sebelum training.

**Akibat untuk aplikasi** (dikerjakan setelah v0.2.0, saat model asli dipasang):
- Daftar kelas **tidak lagi ditulis tetap di kode**. Nama, urutan, warna, dan shortcut diambil dari metadata model yang terpasang, sehingga model 13 kelas dan model 16 kelas sama-sama bisa dipakai. Frontend sudah membaca kelas dari `/api/segmentation/classes`.
- Setiap hasil menyimpan versi model dan versi daftar kelas (F8). Kolom per kelas di `segmentation_log.csv` ditambah lewat migrasi kolom yang sudah ada (`_ensure_log_columns`); baris lama diisi kosong. Export Excel dan COCO memakai daftar kelas dari hasil itu sendiri.
- Kalau model 16 kelas dipakai, warna kelas perlu tiga warna tambahan yang tetap bisa dibedakan, dan shortcut keyboard bertambah (mis. R, T, Y).
- Selama refactor v0.2.0, 13 kelas Chula tetap menjadi kontrak (lihat `refactor/01-spesifikasi-v0.1.0.md`).

**Hitungan 1.000 eritrosit:** di Sardjito, kelas `Uncategorised` juga berisi objek **bukan eritrosit** (limfosit, neutrofil, platelet, artefak), selain eritrosit yang tidak bisa dinilai (bertumpuk, ghost cell). **Keputusan (dikonfirmasi pengguna 2026-11-23): `Uncategorised` tidak dihitung ke target 1.000.** Kelas ini tetap disimpan dan ditampilkan, tetapi dipisahkan dari jumlah eritrosit di progres akuisisi dan di laporan.

**Kemungkinan model multi-label (rencana, belum diputuskan; dicatat 2026-11-23).** Ini pertanyaan eksperimen di `../sardjito-rbc-eksperimen`, bukan keputusan aplikasi. Usulannya satu detektor dengan tiga kepala atribut per sel: ukuran (pilih satu: mikrosit, normosit, makrosit), bentuk (multi-label: normal, ovalosit, target, stomatosit, sferosit, teardrop, burr, fragmentosit, dan seterusnya), dan warna (pilih satu: normokrom, hipokrom). Alasannya:
- label dokter Sardjito (`label-asli.xlsx`) sudah berbentuk ukuran, bentuk, dan warna, dan bentuknya kadang lebih dari satu;
- kelas seperti Microcytic Hypochromia sebenarnya gabungan atribut.

Kelas tunggal tetap diturunkan dari atribut dengan aturan yang sama seperti mode review "Ukuran, bentuk, warna" (F15), supaya perbandingan dengan Chula dan laporan lama tetap jalan.

Hal yang perlu diuji di repo eksperimen:
- Chula hanya punya satu label per sel; atribut yang tidak diketahui diabaikan saat menghitung loss (*partial label*).
- Ukuran mungkin lebih baik **diukur** dari luas mask dengan kalibrasi piksel ke µm (mikrometer objektif, perbesaran tetap) daripada ditebak model.
- Evaluasi per atribut (F1 per bentuk, akurasi ukuran dan warna, kappa dengan dokter per atribut), bukan satu akurasi kelas.

Yang perlu dijaga di aplikasi supaya model seperti ini bisa dipasang tanpa rombak ulang:
- Metadata model menyatakan jenis keluarannya: `single` (kelas tunggal) atau `attributes` (daftar atribut dan nilainya).
- Kontrak deteksi mendapat field opsional `attributes` di samping `classIndex`. Untuk model kelas tunggal, field ini kosong. `classIndex` tetap diisi kelas turunan.
- File perbandingan F15: kalau model atribut, kolom Pendapat Saya menjadi Ukuran, Bentuk, Warna, dan kelas turunan, sama dengan format Pendapat Dokter di mode atribut.
- Hitungan 1.000 eritrosit tidak berubah.

## 8. Catatan regulasi (untuk dibahas)

Kalau hasilnya dipakai untuk keputusan skrining, aplikasi ini bisa tergolong perangkat lunak alat kesehatan. Ini perlu dibahas dengan tim klinis atau institusi: izin edar Kemenkes, standar IEC 62304 (siklus hidup software medis) dan ISO 14971 (manajemen risiko), serta validasi klinis model sebelum dipakai di luar riset.
