# Brief UI/UX v0.3.0 (usulan)

Status: **dikonfirmasi sebagian oleh pengguna (2026-11-23).** Butir bertanda (asumsi) belum dikonfirmasi.

Perombakan dikerjakan setelah refactor v0.2.0, dengan skill frontend-design. Tidak perlu ACC dosen pembimbing (dikonfirmasi 2026-11-23). Prototipe acuan adalah kanvas Artifact baru, bukan mockup lama. Layar desain dibuat sebagai Artifacts dengan gambar sintetis (tanpa data pasien).

## 1. Subjek, pengguna, tugas utama

- **Subjek**: citra apusan darah tepi dengan pewarnaan Wright/Giemsa (eritrosit merah muda, inti dan granula ungu), dilihat lewat kamera mikroskop.
- **Tempat pakai**: unit kesehatan di daerah 3T (terdepan, terluar, tertinggal). Perangkatnya **Jetson Orin Nano** yang dipasang ke **mikroskop cahaya**. Laptop dipakai untuk pengembangan dan riset.
- **Pengguna**: dokter, laboran, peneliti, dan mahasiswa. Pengalaman mereka dengan aplikasi beragam, jadi UI harus bisa dipakai tanpa dijelaskan, tetapi tetap efisien untuk pengguna rutin.
  - Laboran/operator: mengambil citra di mikroskop (tab Capture).
  - Dokter: mereview klasifikasi sel dan memberi verdict (tab Segmentasi).
  - Peneliti/mahasiswa: batch, export dataset, statistik, pengaturan model.
  - (asumsi) Mata sering berpindah antara okuler dan layar.
- **Tugas utama**:
  - Capture: mendapat citra fokus yang benar-benar tajam sampai pinggir, lalu menyimpannya dengan ID pasien yang benar, sampai minimal 1.000 eritrosit per pasien terkumpul (biasanya sekitar 15-20 citra).
  - Segmentasi: memeriksa sel satu per satu dengan cepat, mengoreksi kelas, dan memberi verdict, lalu export.

## 2. Masalah UI sekarang

Dari pengguna (2026-11-23):
- Tampilan terlalu generik dan tidak profesional.
- Tombol tidak dikelompokkan.
- Banyak fitur baru terlihat setelah scroll (statistik, muat model, dst.).
- Fitur masih miskin.

Dari audit kode:

1. Tampilan default framework: palet slate/biru gaya Tailwind dan font sistem, tanpa identitas.
2. Toolbar Segmentasi terlalu padat. Sekitar 15 kontrol sejajar (pilih gambar, muat hasil, jalankan, simpan, tambah sel, ukuran sel, nomor sel, koreksi massal, dst.) tanpa pengelompokan menurut tahap kerja.
3. Pengaturan untuk developer (path model, ambang confidence) bercampur dengan alat review dokter.
4. Urutan kerja Capture tidak terlihat: folder simpan dipilih terpisah dari ID pasien, dan tombol Save mati tanpa penjelasan sampai folder dipilih.
5. Kualitas fokus ada di panel terpisah dari stream, sehingga mata harus berpindah saat memutar fokus.
6. Bahasa campur: "Capture", "Save" vs "Lokasi Simpan", "Ringkasan Folder".
7. Warna latar UI ikut memengaruhi persepsi warna pewarnaan sel (latar kebiruan).

## 3. Ukuran keberhasilan

- Capture sampai simpan satu citra: [ISI: target, ukur dulu di UI lama].
- Review satu gambar (~[ISI] sel) oleh dokter: [ISI: target].
- Operator baru bisa menyelesaikan satu sesi capture tanpa dijelaskan.
- Tidak ada fitur yang hilang (cek inventaris di `02-rencana-v0.3.0.md`).

## 4. Batasan tetap

- Offline: font disimpan di `static/fonts/`, tanpa CDN.
- Tanpa build step (HTML + CSS + script klasik).
- 13 warna kelas sel adalah data, tidak ikut tema.
- Shortcut tetap: Spasi/Enter di Capture, shortcut koreksi sel di Segmentasi.
- Ringan di Jetson: tanpa animasi berat dan tanpa efek blur/backdrop.
- Kontrak backend v0.2.0 tidak berubah. Perombakan hanya menyentuh `templates/` dan `static/`.
- Layar (dikonfirmasi 2026-11-23): **layar sentuh, bisa juga monitor biasa** dengan mouse/keyboard. Jadi target sentuh minimal 44 px (48 px untuk aksi rutin), tidak ada fungsi yang hanya muncul saat hover, zoom gambar dengan pinch dan tombol, shortcut keyboard hanya sebagai tambahan (bukan satu-satunya cara), dan input ID pasien harus nyaman dengan keyboard layar. Ukuran layar sentuh **10-12 inci** (dikonfirmasi 2026-11-23; kira-kira 1280x800 sampai 1920x1200), dan bisa ditambah monitor lewat HDMI. **Tanpa scroll halaman**: tata letak mengisi layar, hanya panel yang boleh scroll di dalamnya.
- Konteks 3T: offline, listrik bisa putus (pekerjaan tidak boleh hilang), dan bantuan teknis jauh. Status perangkat (kamera, model, sisa penyimpanan) harus selalu terlihat.
- Hasil model adalah **alat bantu, bukan diagnosis**, dan UI harus menyatakannya dengan jelas. Selama model masih mock, statusnya harus terlihat mencolok.

## 5. Kebutuhan dari skenario lama

Diambil dari `mockup-ui-redesign/SKENARIO-PENGGUNAAN.md` dan `CATATAN-DESAIN.md` (folder itu dihapus 2026-11-23 atas permintaan pengguna; desainnya tidak dipakai, hanya kebutuhan fiturnya). ID asli dipertahankan.

**Akuisisi**
- K-A1 Satu kesimpulan kesiapan ("Siap ambil", "Perlu fokus", dst.) yang terbaca sekilas bersama stream. Detail teknis hanya bila diminta.
- K-A2 Alur ambil lalu simpan tanpa dialog pada kasus normal. Keputusan yang tidak biasa (ID berubah, sudah tersimpan, buram) ditampilkan di area aksi, bukan modal bertingkat.
- K-A3 Ambil citra **tidak boleh menimpa** citra yang belum tersimpan. Setiap capture masuk riwayat sesi dengan statusnya.
- K-A4 Kalau Simpan tidak bisa dipakai, UI menyebut syarat yang belum terpenuhi (mis. "Isi ID pasien dulu").
- K-A5 Umpan balik simpan yang jelas (nama file, nomor), dan penghitung dengan arti tegas (sesi ini atau total pasien).
- K-A6 Status ketiga prasyarat sesi (kamera, ID pasien, folder) terlihat sekaligus.

**Fokus**
- K-B1 "Puncak belum terkonfirmasi" punya penanda sendiri, bukan abu-abu netral, disertai instruksi tindakan.
- K-B2 Status fokus terlihat tanpa memindahkan pandangan dari stream.
- K-B3 Peringatan pinggir lemah dibedakan dari fokus keseluruhan, dengan saran (cek kemiringan preparat).
- K-B4 Penilaian kualitas tampil bersama citra hasil ambil saat operator memutuskan.
- K-B5 "Simpan tetap" dan "Ulangi" setara dan cepat. Membuang citra buram adalah tindakan sadar.
- K-B6 Metrik teknis (tile, Tenengrad, Laplacian) hanya detail opsional. Skor CLIP diberi label eksperimental selama belum dikalibrasi.

**Kegagalan**
- K-C1 Pesan galat persisten (tidak hilang sendiri) dan berbeda dari notifikasi sukses, tidak hanya lewat warna.
- K-C2 Pesan galat menyebut apa yang gagal (kamera, simpan, koneksi aplikasi), kemungkinan penyebab, dan tindakan berikutnya.
- K-C3 Tombol pemulihan di tempat: "Coba simpan lagi", "Pilih folder lain", "Sambungkan ulang kamera".
- K-C4 Citra yang gagal tersimpan tetap terlihat dengan status "Belum tersimpan" dan tidak tertimpa.
- K-C5 Galat jaringan atau server tertangani dan tampil sebagai "Terputus dari aplikasi", bukan UI yang diam.
- K-C6 Pemulihan mempertahankan pengaturan sesi (kamera, resolusi, ID pasien, folder). Lihat UC-10.
- K-C7 Stream beku (kamera "terhubung" tetapi gambar tidak berubah) terdeteksi.

**Perubahan backend yang dibutuhkan** (dikerjakan setelah v0.2.0):
- `/api/save` mengembalikan penyebab galat (disk penuh, folder hilang, izin), dengan cek ruang disk dan folder sebelum menulis.
- Server atau klien mendukung lebih dari satu citra belum tersimpan.
- Deteksi kamera beku.

## 6. Pertanyaan terbuka

1. Kondisi ruangan: terang atau diredupkan? Sementara tema terang menjadi default, dengan tema gelap untuk ruang redup.
2. ~~Sentuh atau tidak?~~ Sentuh dan monitor biasa (dijawab 2026-11-23). ~~Ukuran layar sentuh?~~ 10-12 inci, plus monitor HDMI opsional.
3. Fitur apa yang dirasa kurang ("fitur miskin")? Lihat usulan di prototipe.
4. Arah gaya: **profesional dan tidak generik** (dari pengguna).
