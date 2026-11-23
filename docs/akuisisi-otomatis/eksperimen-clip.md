# Ringkasan Eksperimen CLIP untuk Quality Gate Citra Apusan Darah Tepi

Riset bersama dosen pembimbing. Ringkasan ini mencatat eksperimen pada notebook `clip_kualitas_apusan.ipynb` di folder `eksperimen-clip/` (di luar repo, satu tingkat di atas folder repo; dijalankan di Google Colab) dan menindaklanjuti bagian "Eksplorasi CLIP" di `rancangan.md` (folder ini). Output mentah ada di `eksperimen-clip/clip_kualitas_apusan-with-output.ipynb`.

Status: **eksplorasi awal.** Belum ada label dokter dan belum ada data defocus asli, sehingga temuan di bawah adalah indikasi, bukan keputusan akhir.

---

## 1. Tujuan

1. Apakah CLIP (zero-shot, pasangan prompt antonim, multi-crop resolusi asli, norma fitur) dapat mendeteksi blur sehalus data mikroskop kita, dan apakah lebih baik dari metrik klasik (Tenengrad)?
2. Apakah skor CLIP untuk semantik (kepadatan, overlap, area kosong, artefak) masuk akal pada gambar asli?
3. Apakah linear probe pada embedding CLIP beku lebih baik dari zero-shot, diuji per pasien?
4. Berapa latensi encoder?

## 2. Setup

| Item | Nilai |
|---|---|
| Lingkungan | Google Colab, GPU T4, Python 3.13 |
| Model | `open_clip` ViT-B-32, bobot `openai`, input 224, encoder gambar 87,8 juta parameter |
| Data | 80 PNG 2592×1944 (MiiCam), `pasien-1` dan `pasien-2` (masing-masing 40), tanggal 27-08, **tanpa label** |
| Patch CLIP | `full`: persegi tengah 1944×1944 diperkecil ke 224. `crops`: grid 3×3 crop 448×448 (resolusi asli, diperkecil ke 224) di ROI tengah 60% frame, skor dirata-rata |
| Metrik klasik | variance Laplacian (`lap_var`), Tenengrad ROI tengah (`teng_center`) dan pinggir (`teng_edge`), rasio pinggir/tengah |
| Prompt | Pasangan antonim per aspek (tajam vs buram, monolayer, kepadatan, bersih) memakai softmax di antara pasangan (gaya CLIP-IQA). Dua skor `gabungan` dari prompt ensembling: `gabungan` (prompt asli catatan, ada negasi dan aspek fokus) dan `gabungan_v2` (tanpa negasi dan tanpa aspek fokus) |
| Fitur lain | `norm|full`, `norm|crops` (norma fitur CLIP, hipotesis MA-CLIP) |
| Eksperimen blur sintetis | 15 gambar per pasien × sigma Gaussian {0, 1, 2, 3, 5, 8} px pada resolusi asli = 180 varian |
| Linear probe | Regresi logistik (C=0,1) pada rata-rata embedding crop, label tajam (σ=0) vs buram (σ≥2), uji leave-one-patient-out |

Catatan teknis: open_clip memberi peringatan **QuickGELU mismatch** (`ViT-B-32` dengan bobot `openai`). Perbaikan yang disarankan: `MODEL_NAME = 'ViT-B-32-quickgelu'`. Belum dijalankan ulang.

## 3. Hasil pada 80 gambar asli

Rata-rata per pasien:

| Metrik | pasien-1 | pasien-2 |
|---|---|---|
| `lap_var` | 5,49 | 5,09 |
| `teng_center` | 38,3 | 25,9 |
| `teng_edge` | 31,0 | 18,5 |
| rasio pinggir/tengah | 0,82 | 0,72 |
| `tajam_vs_buram\|crops` | 0,088 | 0,102 |
| `monolayer\|crops` | 0,19 | 0,28 |
| `kepadatan\|crops` | 0,55 | 0,37 |
| `gabungan\|crops` | 0,46 | 0,42 |
| `gabungan_v2\|crops` | 0,56 | 0,52 |
| `norm\|crops` | 10,09 | 10,45 |

- Dua pasien sangat berbeda (Tenengrad 38 vs 26, kepadatan 0,55 vs 0,37). Di montase, gambar Tenengrad rendah tampak dari sediaan yang pucat dengan burr cell (dugaan pasien-2, karena judul montase tidak memuat nama pasien).
- Karena itu matriks korelasi 80 gambar **terkacaukan perbedaan antar pasien**. Analisis yang benar adalah di dalam pasien (bagian 6).
- Rasio pinggir/tengah 0,72–0,82 menunjukkan pinggir frame lebih lemah gradiennya (bisa lengkung bidang optik, belum diverifikasi).

## 4. Eksperimen blur sintetis

Metrik yang baik harus turun monoton saat sigma naik. `rho` = korelasi Spearman antara sigma dan skor di dalam tiap gambar (dirata-rata). AUC memisahkan σ=0 dari σ=k (skor tinggi = tajam; di bawah 0,5 berarti arah terbalik).

### Putaran 1 (blur saja) dan koreksi

`lap_var` mendapat AUC 1.00 di semua sigma dan rho -1,00; linear probe juga 1.00. Hasil itu **mencurigakan**: blur Gaussian yang diterapkan setelah capture ikut menghapus noise sensor, padahal defocus optik tidak menghapusnya.

Estimasi noise sensor dari gambar asli (MAD residual) memberi `noise_sd` rata-rata **0,49** tingkat abu-abu (skala 0–255). Karena jumlah kuadrat koefisien kernel Laplacian 3×3 adalah 20, noise murni dengan sd ini memberi variance sekitar 0,49² × 20 ≈ **4,8**, mendekati `lap_var` asli yang 5,1–5,5. Jadi `lap_var` sebagian besar berada di floor noise.

### Putaran 2 (noise dikembalikan setelah blur)

| Metrik | rho | AUC σ=1 | σ=2 | σ=3 | σ=5 | σ=8 |
|---|---|---|---|---|---|---|
| `teng_center` | -1,00 | 0,60 | 0,71 | 0,81 | 0,93 | 0,99 |
| `teng_edge` | -1,00 | 0,58 | 0,66 | 0,71 | 0,81 | 0,94 |
| `lap_var` | -0,87 | **0,35** | 0,72 | 0,83 | 0,85 | 0,84 |
| `tajam_vs_buram\|full` | -0,94 | 0,55 | 0,61 | 0,69 | 0,82 | 0,86 |
| `tajam_vs_buram\|crops` | **+0,90** | 0,38 | 0,37 | 0,24 | 0,06 | 0,00 |
| `norm\|crops` | **+1,00** | 0,19 | 0,02 | 0,00 | 0,00 | 0,00 |
| `norm\|full` | +0,99 | 0,45 | 0,38 | 0,31 | 0,19 | 0,06 |
| `bersih\|crops` | +0,93 | 0,43 | 0,33 | 0,29 | 0,08 | 0,00 |
| `kepadatan\|crops` | -1,00 | 0,59 | 0,68 | 0,76 | 0,96 | 1,00 |
| `gabungan\|crops` | -0,81 | 0,36 | 0,45 | 0,59 | 0,85 | 1,00 |
| `gabungan_v2\|crops` | -0,88 | 0,49 | 0,48 | 0,68 | 0,94 | 1,00 |
| `monolayer\|crops` | -0,02 | 0,46 | 0,34 | 0,30 | 0,35 | 0,68 |

Perubahan dari putaran 1 ke 2:
- `lap_var`: dari 1.00 di semua sigma menjadi tidak monoton (naik dulu di σ=1, puncak 0,93 pada kurva ternormalisasi). Ini mengonfirmasi bias noise. Kenaikan di σ=1 kemungkinan dipengaruhi noise putih suntikan yang tidak sama dengan noise asli kamera.
- Tenengrad, `norm|crops`, dan `tajam_vs_buram|crops` praktis tidak berubah, jadi bukan artefak noise.

## 5. Linear probe (leave-one-patient-out)

Akurasi probe dengan ambang Youden dari data latih: 0,911 (uji di pasien-1) dan 1,000 (uji di pasien-2).

AUC per sigma (positif = buram):

| Uji di | Metode | σ=1 | σ=2 | σ=3 | σ=5 | σ=8 |
|---|---|---|---|---|---|---|
| pasien-1 | linear_probe | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| pasien-1 | tenengrad | 0,63 | 0,74 | 0,84 | 0,95 | 0,99 |
| pasien-1 | clip_zeroshot_crops | 0,47 | 0,53 | 0,33 | 0,06 | 0,00 |
| pasien-1 | clip_gabungan_crops | 0,29 | 0,46 | 0,70 | 0,92 | 1,00 |
| pasien-2 | linear_probe | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| pasien-2 | tenengrad | 0,69 | 0,87 | 0,96 | 1,00 | 1,00 |
| pasien-2 | clip_zeroshot_crops | 0,24 | 0,12 | 0,02 | 0,00 | 0,00 |
| pasien-2 | clip_gabungan_crops | 0,33 | 0,42 | 0,56 | 0,88 | 1,00 |

AUC probe 1.00 bahkan di σ=1, yang saat latihan berlabel "tajam". Hasil sempurna itu tetap muncul setelah noise dikembalikan.

### Uji transfer ke gambar asli

Probe dilatih pada semua data sintetis lalu diterapkan ke 80 gambar asli:
- Rata-rata skor probe (tinggi = buram): pasien-1 -11,32 dan pasien-2 -10,84, keduanya jauh di sisi "tajam".
- Korelasi probe dengan `teng_center` di dalam pasien: **+0,23** (pasien-1) dan **-0,04** (pasien-2). Arah yang benar seharusnya negatif dan kuat. Dengan n=40, |ρ|>0,31 baru signifikan, jadi keduanya tidak signifikan.

Kesimpulan: probe **tidak transfer** ke gambar asli. Kemungkinan besar ia belajar membedakan "belum diproses vs sudah diproses pipeline blur" (hanya σ=0 yang tidak melewati blur, noise suntikan, dan pemotongan ke uint8).

## 6. Korelasi di dalam pasien terhadap Tenengrad (`teng_center`)

n=40 per pasien, |ρ|>0,31 signifikan (p<0,05):

| Metrik | pasien-1 | pasien-2 |
|---|---|---|
| `focus_logbook` | +0,72 | +0,39 |
| `lap_var` | +0,74 | +0,41 |
| `teng_edge` | +0,60 | +0,35 |
| `norm\|crops` | **-0,60** | **-0,52** |
| `tajam_vs_buram\|crops` | -0,54 | -0,50 |
| `kepadatan\|crops` | -0,27 | 0,00 |
| `gabungan\|crops` | -0,15 | +0,04 |
| `gabungan_v2\|crops` | -0,12 | +0,13 |
| `probe_blur` | +0,23 | -0,04 |

## 7. Latensi encoder (T4, bukan Orin Nano)

| Batch | Waktu |
|---|---|
| 1 patch | 10,0 ms |
| 10 patch (1 field: 1 full + 9 crop) | 11,1 ms |

Mengirim 10 patch sekaligus hampir gratis. Encoder bukan bottleneck; baca file dan metrik klasik di CPU lebih lama. Latensi di Orin Nano belum diukur (butuh ekspor ONNX lalu TensorRT FP16).

## 8. Temuan

1. **CLIP zero-shot tidak cocok untuk fokus.** Arah skor terbalik (gambar blur dianggap lebih "tajam" dan "bersih"), dan skor `tajam_vs_buram` rata-rata hanya sekitar 0,09–0,10 sehingga hampir semua gambar dianggap buram. Pada blur ringan (σ=1–2) tidak ada metrik CLIP zero-shot yang di atas kebetulan, sedangkan Tenengrad 0,60–0,71.
2. **Tenengrad tahan terhadap perubahan protokol** dan turun monoton di setiap gambar (rho -1,00). AUC pooled untuk blur ringan rendah (0,60 di σ=1) karena variasi antar gambar sebesar efek blurnya. Jadi ia cocok untuk **autofokus** (perbandingan relatif pada lapang pandang yang sama), bukan untuk ambang absolut.
3. **`lap_var` (metrik `focus_score` aplikasi) tidak layak untuk autofokus.** Ia berada di floor noise (~4,8 dari ~5,5) dengan rentang dinamis sempit. Korelasi dalam pasien dengan Tenengrad (+0,74 dan +0,41) menunjukkan ada komponen konten, tetapi keduanya mungkin sama-sama dikacaukan isi gambar (kepadatan, kontras pewarnaan).
4. **Linear probe dari blur sintetis dibuang** sebagai detektor fokus karena tidak transfer ke gambar asli.
5. **Skor semantik (`kepadatan`, `gabungan`, `gabungan_v2`) hampir independen dari Tenengrad di dalam pasien** (ρ -0,27 sampai +0,13, tidak signifikan) sehingga layak jadi gerbang semantik terpisah. Sinyalnya sebagian besar adalah **kepadatan sel** (korelasi 0,91 dan 0,87 dengan `kepadatan` di data asli). Urutan visual masuk akal: skor tinggi = gambar padat, tajam, terpisah rapi; skor rendah = gambar pucat dan jarang. Skor ini baru bereaksi pada blur berat (σ≥3).
6. **Pasangan prompt `monolayer` terbalik**: gambar jarang dan pucat mendapat skor tertinggi, sedangkan gambar padat dianggap "menumpuk". Disarankan dibuang atau diganti.
7. **`norm|crops` menarik tetapi belum terbukti.** Arahnya terbalik dari hipotesis MA-CLIP (norma naik saat blur), konsisten di data sintetis (setelah tanda dibalik, AUC ≈ 0,81 / 0,98 / 1,00 untuk σ=1 / 2 / ≥3) dan di gambar asli (-0,60 dan -0,52 terhadap Tenengrad, di kedua pasien). Tetapi acuannya adalah Tenengrad yang bukan kebenaran independen.
8. **Ada sumbu terkait ketajaman di embedding crop** (`norm|crops` dan `tajam_vs_buram|crops` sama-sama sekitar -0,5 terhadap Tenengrad, arah terbalik). Zero-shot memakainya dengan arah yang salah. Jika mau dimanfaatkan, probe harus dilatih dengan defocus asli, bukan blur sintetis.

## 9. Pelajaran metodologis dan koreksi

- Dua prediksi awal saya **salah**: (a) `lap_var` diperkirakan rata terhadap sigma setelah noise dikembalikan, ternyata tidak monoton dan naik di σ=1; (b) linear probe diperkirakan turun dari 1.00, ternyata tetap 1.00, dan baru terbukti tidak transfer lewat uji ke gambar asli.
- Blur sintetis Gaussian setelah capture bukan defocus optik: noise ikut hilang, dan hanya σ=0 yang tidak melewati pipeline pemrosesan sehingga bisa diisyaratkan oleh probe.
- Korelasi gabungan dua pasien menyesatkan; selalu hitung di dalam pasien.
- Tenengrad tidak bisa dijadikan kebenaran untuk menilai metrik lain (melingkar).

## 10. Batas eksperimen

- Hanya 2 pasien dan 40 gambar per pasien.
- Tidak ada label dokter dan tidak ada data defocus asli.
- Uji transfer memakai Tenengrad sebagai proxy fokus, dan Tenengrad dipengaruhi isi gambar.
- Crop CLIP hanya mencakup 60% tengah frame, dan patch `full` hanya persegi tengah 1944×1944 (sisi kiri dan kanan terbuang). **Dokter akan menganotasi citra penuh**, jadi cakupan ini belum sesuai kebutuhan.
- Latensi diukur di T4, bukan Orin Nano.

## 11. Keputusan sementara

- **Fokus**: Tenengrad per tile di **seluruh frame** (peta ketajaman lalu ringkasan per gambar, misalnya persentil ke-10 atau fraksi tile yang tajam). Bukan CLIP dan bukan `lap_var`.
- **Semantik**: CLIP (`kepadatan`/`gabungan_v2`, prompt diperbaiki) sebagai gerbang tambahan setelah fokus lolos.
- **Kebenaran acuan**: label dokter pada citra penuh (layak dianotasi atau tidak, dengan alasan).

## 12. Langkah berikutnya

1. **Perbarui notebook untuk citra penuh**: grid crop CLIP meliputi seluruh frame, peta Tenengrad per tile, ringkasan per gambar.
2. **Lembar penilaian untuk dokter**: gambar penuh dengan ID acak (tanpa nama pasien dan skor), plus CSV isian (layak/tidak layak dan alasan: buram, pinggir buram, overlap, kosong/jarang, artefak). Sekitar 100–200 gambar dengan variasi fokus.
3. **Z-stack sungguhan**: 8–10 lapang pandang per pasien, 7–9 posisi fokus per lapang pandang. Menguji autofokus (Tenengrad seluruh frame vs tengah, kemungkinan lengkung bidang), `norm|crops`, dan kestabilan skor semantik di sekitar fokus.
4. Jalankan ulang dengan `ViT-B-32-quickgelu`, dan coba MobileCLIP-S1/S2 (kandidat Orin Nano).
5. Ekspor encoder ke ONNX (FP16) untuk mengukur ukuran dan latensi (target akhir Orin Nano dengan TensorRT).
6. Konfirmasi dengan dokter: apakah seluruh frame (termasuk pinggir) dianotasi.

## 13. Reproduksi

- Notebook (di luar repo, folder induk): `eksperimen-clip/clip_kualitas_apusan.ipynb` (Colab, GPU T4). Parameter di sel Konfigurasi.
- Data (di luar repo, folder induk, data pasien): `data-hasil-akuisisi/27-08/pasien-1` dan `pasien-2` diunggah ke `MyDrive/.../27-08`.
- Putaran 2 memakai perbaikan noise (`noise_sd` dari MAD residual, noise Gaussian putih ditambahkan setelah blur) dan koreksi `cv2.Laplacian(..., cv2.CV_32F)` karena OpenCV 5 di Colab menolak float32 → float64.
