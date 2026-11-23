# Rancangan: Akuisisi Otomatis untuk Mikroskop Cerdas (autofokus + stage snake + auto-capture)

Status: **hanya rancangan, belum ada kode** (sesuai permintaan). Tidak ada file proyek yang diubah.

> **Catatan 2026-11-23 (refactor v0.2.0):** rujukan `app.py:<baris>` di dokumen ini mengacu ke monolith v0.1.0. Sejak v0.2.0, kodenya dipindah apa adanya:
> - `compute_focus_score` dan `is_blank_frame` ada di `quality.py`;
> - `CameraManager`, callback ToupCam, dan `gen_mjpeg` ada di `camera.py`;
> - `api_save`, `next_iteration_from_folder`, dan `save_lock` ada di `capture.py` dan `csvlog.py`.
>
> Pertanyaan "kode hardware di `app.py` atau file baru" terjawab oleh struktur modul: kode motor dan stage menjadi modul baru sendiri.

## Context

Aplikasi capture (Flask monolith: `app.py`, `static/js/app.js`, `templates/index.html`) saat ini bersifat manual: operator menekan Capture, lalu Save. Skor fokus hanya informasi (badge), dihitung sekali saat capture, dan tidak memblokir apa pun. Tujuan akhirnya adalah mendampingi mikroskop cerdas: motor menggerakkan fokus (Z) dan stage XY mengikuti pola snake, dan gambar hanya disimpan jika kualitasnya layak.

Temuan dari data 27-08/pasien-1 yang membentuk rancangan ini:
- Variance Laplacian (`compute_focus_score`, app.py:558) berkisar 5.1–6.1 pada 40 gambar dan hampir rata antar wilayah (rasio pinggir/tengah 0,9–0,99) padahal pinggir jelas lebih buram. Skor itu kemungkinan mengukur noise sensor, bukan fokus. Tidak cocok untuk autofokus.
- Blur pinggir kemungkinan field curvature optik. Autofokus harus mengoptimalkan wilayah tengah.
- Eksplorasi codebase: tidak ada kode motor/serial/GPIO sama sekali; `CameraManager` hanya menyimpan `last_frame`; `captured_frame` adalah satu slot global; logika save ada inline di `api_save` (app.py:701).

Keputusan user: motor = driver stepper langsung via GPIO Jetson; sumbu = Z + stage XY berpola snake; kriteria "layak simpan" mau dieksplorasi dengan CLIP.

## Arsitektur yang diusulkan

Tiga lapis, dari bawah ke atas. Tiap lapis bisa dites sendiri.

1. **Metrik kualitas gambar** (murni software, tanpa motor)
   - Fokus: Tenengrad (Sobel) setelah Gaussian blur, di ROI tengah (~60% frame), frame diperkecil dulu untuk kecepatan. Dipakai untuk autofokus (perbandingan relatif antar posisi Z), bukan ambang absolut.
   - Kosong/seragam: `is_blank_frame` (app.py:579) dipakai ulang.
   - Semantik (eksplorasi CLIP, lihat bagian di bawah): apakah lapang pandang bermakna.

2. **Lapisan hardware** (abstraksi + implementasi)
   - `MotorAxis` (antarmuka): `move_to(steps)`, `move_relative`, `home()`, `position`, `limits`. Implementasi: `GpioStepperAxis` (Jetson) dan `FakeAxis` (simulasi untuk pengembangan di laptop Windows).
   - `Stage` = dua `MotorAxis` (X,Y) + kompensasi backlash (selalu mendekat dari satu arah).
   - Keamanan: homing dengan limit switch, soft limit, tombol stop darurat di API, timeout gerak.
   - Catatan jujur tentang GPIO Jetson: pembangkitan pulsa STEP dari Python tidak presisi (jitter, ribuan Hz paling banyak) dan bisa kehilangan langkah di bawah beban. Pilihan yang lebih aman: pakai PWM hardware Jetson, atau offload ke mikrokontroler kecil (Arduino/RP2040) yang menerima perintah "gerak N langkah" lewat serial. Ini perlu keputusan sebelum implementasi.

3. **Orkestrator akuisisi** (thread latar di server)
   - State machine: `IDLE → HOMING → MOVE_TO_FIELD → SETTLE → AUTOFOCUS → QUALITY_GATE → CAPTURE_SAVE → NEXT_FIELD`, plus `PAUSED`, `ERROR`.
   - Membaca frame dari `camera.last_frame` (bukan `cap.read()` baru, karena jalur OpenCV bersifat pull dan akan berebut dengan `/stream`).
   - Menyimpan lewat fungsi save yang diekstrak dari `api_save` (app.py:701-760) supaya penomoran iterasi (`next_iteration_from_folder`, dilindungi `save_lock`) dan `capture_log.csv` dipakai ulang.

## Pola scan snake (serpentine raster)

- Grid lapang pandang ditentukan dari area scan (sudut kiri atas dan kanan bawah) dan ukuran field-of-view dalam langkah motor (perlu kalibrasi piksel → langkah motor → mikron).
- Baris bergantian arah (kiri→kanan, kanan→kiri) untuk meminimalkan perjalanan stage.
- Overlap antar lapang pandang 10–20% agar sel di tepi yang terpotong tertangkap utuh di field tetangga (penting karena pinggir buram ikut terpotong jika pakai crop tengah).
- Backlash: pada balik arah, lewati target lalu kembali dari arah standar.
- Area yang diprioritaskan: zona **monolayer** apusan (bagian kepala terlalu tebal, ekor terlalu jarang). Ini yang paling cocok disaring oleh gate semantik.

## Strategi autofokus

- Saat mulai: sapuan kasar pada rentang Z lebar, langkah besar, cari puncak skor fokus.
- Tiap field berikutnya: pencarian halus di sekitar Z terakhir (golden-section atau hill-climbing dengan langkah mengecil), bukan sapuan penuh, supaya cepat.
- Peta fokus: simpan Z terbaik per field dan prediksi Z field berikutnya (tilt preparat, apusan tidak rata).
- Setelah mencapai Z terbaik: ambil beberapa frame, median skor, untuk menahan noise.
- Batas iterasi dan fallback: jika puncak tidak ditemukan (field kosong, tidak ada struktur), tandai field sebagai "dilewati" dan lanjut, jangan berputar tanpa akhir.
- Karena kontras gambar rendah (sel pucat pada latar kuning), kemungkinan perlu CLAHE ringan pada kanal L sebelum menghitung metrik. Ini dievaluasi, bukan diasumsikan.

## Eksplorasi CLIP (untuk kriteria "layak simpan")

Sumber: `riset-clip.md` (folder ini) (kriteria monolayer, arsitektur gate real-time, deployment Jetson Orin Nano). Rancangan di bawah digabung dengan ringkasan itu. Dua hal diselaraskan:

- **Koreksi untuk ringkasan:** langkah "blur check cv2 Laplacian" di pipeline gate sebaiknya diganti metrik Tenengrad di ROI tengah. Pada data pasien-1, variance Laplacian mengukur noise (skor 5.1–6.1, rata antar wilayah), jadi tidak bisa menjadi filter cepat yang andal. Prinsipnya tetap sama: klasik dulu, murah, reject cepat.
- **Sejalan dengan ringkasan:** CLIP dipakai sebagai skor semantik (overlap, area kosong, sebaran sel, artefak), ensemble dengan metrik blur klasik, text embedding di-precompute, ambang dikalibrasi dengan ROC/Youden's J dari label operator.

Pipeline gate real-time:
```
frame → blank check → Tenengrad ROI tengah (reject cepat)
      → image encoder CLIP (kecil) → cosine vs text embedding precomputed
      → skor monolayer → ambang (Youden's J) → simpan / lewati
```

Deployment Jetson Orin Nano (dari ringkasan): pakai MobileCLIP / TinyCLIP / ViT-S/16 (bukan ViT-B/32) → ekspor ONNX → TensorRT FP16 (INT8 dengan kalibrasi belakangan). Hanya image encoder yang jalan di perangkat; text embedding dihitung di luar dan dimuat statis. Cek JetPack, varian Orin Nano (4GB/8GB/Super), kompatibilitas TensorRT, dan bottleneck preprocessing (resize/normalisasi, idealnya GPU via VPI). Laptop Windows dipakai untuk pengembangan dengan PyTorch/OpenCLIP dulu.

Prompt awal untuk zero-shot baseline: positif ("a well-spread blood smear with evenly distributed cells", "a monolayer blood smear image with minimal empty space", ...) dan negatif ("heavily overlapping cells", "large empty background", "sparse non-uniform cell distribution"). Prompt "a blurry blood smear image" dipertahankan hanya sebagai pembanding; penentu fokus tetap metrik klasik.

Catatan data: split evaluasi/probe **per pasien/slide** (GroupShuffleSplit), bukan per gambar, supaya tidak bocor.

Pertimbangan:

- **Kekuatan:** baik untuk pertanyaan semantik: apakah ada sel, apakah lapang pandang terlalu padat/menumpuk, terlalu tipis, atau ada artefak/debu.
- **Kelemahan untuk fokus:** CLIP memakai input 224×224. Downsampling dari 2592×1944 menghapus informasi blur halus, dan zero-shot CLIP dikenal lemah untuk blur ringan. Jadi **jangan jadikan CLIP penentu fokus**. Fokus tetap metrik klasik (cepat, dipakai berulang dalam loop autofokus).
- **Biaya:** jalankan CLIP sekali per field (bukan per frame dalam loop autofokus). Latensi aktual di Orin Nano belum diukur, jadi benchmark termasuk tahap 2.
- **Cara pakai yang disarankan, dari yang paling murah:**
  1. Zero-shot dengan prompt teks ("lapang pandang sel darah merah yang tersebar rapi", "gambar buram", "gambar kosong", "sel menumpuk"). Dipakai sebagai baseline.
  2. **Linear probe**: ekstrak embedding CLIP dari gambar berlabel, latih logistic regression. Hampir selalu lebih baik daripada zero-shot untuk domain khusus seperti ini, dan cukup dengan beberapa ratus gambar.
  3. Jika fokus ingin dinilai CLIP juga: pakai tile resolusi asli (crop 224 tanpa diperkecil) atau embedding dari beberapa crop.
- **Protokol evaluasi (inti eksplorasi):**
  1. Kumpulkan sekitar 200+ frame dari mikroskop dengan label: fokus baik/buram, kosong, terlalu tebal/menumpuk, monolayer bagus. Sebagian dibuat dengan sengaja menggeser fokus.
  2. Bandingkan AUC untuk tiap label: metrik klasik (Tenengrad), CLIP zero-shot, CLIP linear probe.
  3. Putuskan pembagian tugas: kemungkinan besar klasik untuk fokus, CLIP linear probe untuk kualitas semantik. Hasil ini menentukan arsitektur gate, bukan sebaliknya.

### Perbaikan CLIP untuk blur ringan (hasil riset literatur)

Masalah intinya dua: (a) input 224×224 membuang informasi blur halus, (b) cosine similarity terhadap satu prompt "blurry" lebih mencerminkan semantik daripada ketajaman. Opsi perbaikan, dari yang paling murah:

1. **Patch resolusi asli, bukan seluruh frame diperkecil.** Model fokus mikroskop yang terbukti (Yang dkk. 2018, BMC Bioinformatics) bekerja pada patch 84×84 piksel pada resolusi asli, memprediksi 11 level defocus (kira-kira 3 px diameter blur per level) dengan kepastian prediksi, F-score biner 0,89 dibanding 0,84 metrik klasik sebelumnya, ~1,1 s per gambar 2048×2048. Untuk CLIP: ambil beberapa crop 224×224 native dari ROI tengah, rata-ratakan embedding atau skor.
2. **Pasangan prompt antonim (CLIP-IQA), bukan cosine mentah.** Bandingkan pasangan ("sharp" vs "blurry") dengan softmax di antara keduanya dan pakai beberapa pasangan deskriptif. Lebih stabil dan bisa menunjukkan penyebab penurunan kualitas.
3. **Sinyal magnitudo fitur (MA-CLIP, 2025, tanpa pelatihan).** Norma fitur gambar CLIP berkorelasi dengan kualitas persepsi dan diabaikan oleh cosine. Menggabungkan cosine dengan magnitudo (Box-Cox + fusi berbasis keyakinan) meningkatkan kinerja CLIP-IQA pada benchmark umum. Catatan: makalahnya tidak menguji blur mikroskop, jadi ini hipotesis untuk diuji, bukan jaminan.
4. **Linear probe pada embedding dengan augmentasi blur sintetis.** Buat pasangan bersih/buram dari gambar fokus (Gaussian atau PSF defocus, ditambah noise Poisson seperti Yang dkk.) sehingga label tidak perlu dilabel manual satu per satu. Latih logistic regression atau klasifikasi ordinal level blur pada embedding CLIP beku. Literatur CLIP juga melaporkan blur sintetis pada few-shot membuat model lebih tahan terhadap isu kualitas ini.
5. **Fine-tune ringan (LoRA/lapisan atas) pada encoder kecil**, jika linear probe belum cukup. Ada bukti pada pencitraan apusan darah bahwa fine-tuning lapisan atas model mobile (MobileViT) mencapai akurasi 99,28% untuk klasifikasi gambar fokus baik (studi lain, bukan CLIP, dan perlu dicek ke sumber aslinya).

**Yang saya ragukan dan perlu diuji, bukan diasumsikan:**
- Apakah CLIP, bahkan dengan perbaikan di atas, mengalahkan Tenengrad untuk blur ringan. Dugaan saya tidak: untuk fokus, metrik klasik atau CNN kecil khusus fokus kemungkinan lebih tepat dan jauh lebih murah. Nilai tambah CLIP ada di sisi semantik (overlap, area kosong, sebaran sel).
- Catatan dari data sendiri: blur pada pasien-1 bersifat halus dan tidak seragam (pinggir lebih buram daripada tengah), persis kasus yang paling sulit bagi CLIP.

**Desain percobaan untuk memutuskan:** pada set berlabel dengan blur sintetis bertingkat dan blur asli, bandingkan AUC dan korelasi Spearman terhadap level blur untuk: Tenengrad, CLIP zero-shot (cosine), CLIP-IQA antonim, + magnitudo, + multi-crop native, linear probe (per-crop), dan CNN fokus kecil ala Yang dkk. Keluaran: tabel per metode, latensi di Orin Nano, dan keputusan pembagian tugas.

Sumber: [CLIP-IQA multiple antonym prompt pairs](https://arxiv.org/abs/2308.13094), [MA-CLIP](https://arxiv.org/abs/2511.09948), [Yang dkk. 2018 focus quality](https://pmc.ncbi.nlm.nih.gov/articles/PMC5853029/), [BATCLIP (kerentanan CLIP terhadap korupsi)](https://arxiv.org/abs/2412.02837), [blood smear MobileViT (PubMed)](https://pubmed.ncbi.nlm.nih.gov/41370363/).

## Gate kualitas sebelum simpan

Urutan murah → mahal, berhenti pada kegagalan pertama:
1. Tidak kosong (`is_blank_frame`).
2. Fokus: skor relatif terhadap puncak autofokus, atau di atas ambang hasil kalibrasi.
3. Semantik (CLIP linear probe, jika hasil eksplorasi mendukung).

Field yang gagal: coba autofokus ulang sekali, lalu dilewati dan dicatat alasannya.

## Perubahan yang perlu dipertimbangkan pada kode yang ada

- `app.py` (monolith): ekstrak logika save dari `api_save` menjadi fungsi terpisah; tambahkan metrik fokus baru; tambahkan endpoint kontrol (mulai/jeda/stop scan, status, jog manual).
- `CameraManager` (app.py:194): sediakan akses aman ke frame terbaru (mis. `get_latest()` di bawah lock); skor fokus live dihitung di jalur frame (callback ToupCam, app.py:427-452, atau `gen_mjpeg`, app.py:529) dan di-cache.
- `static/js/app.js` + `templates/index.html`: badge fokus live di samping `focusBadge`, toggle "Mode Otomatis" di `.toolbar-row`, panel status scan (posisi field, progres, field dilewati), jog manual dan tombol stop.
- `capture_log.csv`: tambah kolom posisi (x, y, z), skor fokus baru, alasan gate, agar setiap gambar bisa ditelusuri ke posisinya.
- Pertimbangan struktur: kode hardware (motor, stage) bisa tetap di `app.py` mengikuti konvensi monolith, atau dipisah ke file baru yang di-import. **Ini perlu konfirmasi**, karena memori proyek mencatat mesin akuisisi menjalankan monolith dan refactor modular tidak boleh disambungkan tanpa bertanya.

## Tahapan usulan (masing-masing bisa diverifikasi tanpa tahap berikutnya)

1. **Fondasi software:** metrik fokus baru + skor live + kalibrasi ambang dari data. Tanpa motor.
2. **Pengumpulan data berlabel + evaluasi CLIP** (protokol di atas), bisa dikerjakan paralel dengan tahap 1. Motor belum dibutuhkan jika fokus digeser manual. Termasuk: zero-shot baseline, linear probe, benchmark latensi MobileCLIP/TinyCLIP (PyTorch lalu TensorRT FP16) di Orin Nano, dan kalibrasi ambang dengan Youden's J.
3. **Lapisan hardware + `FakeAxis`**: dev dan tes state machine di laptop tanpa perangkat keras.
4. **Driver GPIO/kontroler motor asli + kalibrasi** (piksel ↔ langkah ↔ mikron, backlash, limit).
5. **Autofokus pada mikroskop asli**, dimulai dari Z saja.
6. **Scan snake + auto-capture** dengan gate kualitas.

## Verifikasi (saat nanti diimplementasikan)

- Tahap 1: jalankan metrik baru pada folder `Data fix/27-08/pasien-1` dan pada gambar yang sengaja diburamkan; skor harus turun jelas saat fokus digeser dan peka terhadap blur di ROI tengah. Bandingkan dengan variance Laplacian lama.
- Tahap 2: laporkan AUC per metode pada set berlabel yang ditahan (tidak dipakai melatih probe).
- Tahap 3: tes otomatis state machine dengan `FakeAxis` (urutan snake benar, backlash, batas, stop darurat, field dilewati).
- Tahap 4–6: uji di mikroskop dengan preparat nyata; cek tidak ada langkah hilang (kembali ke posisi home, posisi sama), autofokus konvergen dalam jumlah langkah wajar, dan gambar tersimpan sesuai gate.

## Pertanyaan terbuka

1. Motor: GPIO Jetson langsung atau mikrokontroler perantara (lihat catatan jitter di atas)?
2. Apakah ada limit switch/encoder pada Z dan XY?
3. Berapa sisa travel Z dan resolusi langkah per mikron?
4. Apakah hardware tersedia sekarang, atau tahap 1–3 dikerjakan dulu tanpa perangkat?
5. Kode hardware tetap di `app.py` atau dipisah ke file baru?
