# Operasional Perangkat

Status: **kerangka, isi menunggu diskusi** (dicatat 2026-11-23). Dokumen ini mengumpulkan semua keputusan operasional untuk perangkat di unit kesehatan 3T. Bagian bertanda `[ISI: ...]` belum diputuskan.

## 1. Perangkat dan perangkat lunak

| Item | Spesifikasi |
|---|---|
| Komputer | NVIDIA Jetson Orin Nano, JetPack [ISI: versi] |
| Penyimpanan | [ISI: microSD/NVMe, kapasitas] |
| Layar | Layar sentuh [ISI: ukuran] atau monitor HDMI |
| Mikroskop | Mikroskop cahaya [ISI: merek/objektif] |
| Kamera | [ISI: mis. MiiCam MC500], driver: SDK ToupCam (`vendor/toupcam/arm64/`) |
| Daya | [ISI: UPS/power bank, perilaku saat listrik padam] |
| Aplikasi | Versi terpasang dicatat di bar status. Jalankan dengan `run.sh` |

## 2. Instalasi dan serah terima

1. [ISI: siapa yang memasang, di mana image/sistem disiapkan]
2. Langkah instalasi: lihat README (Ubuntu/Linux), termasuk udev rule ToupCam.
3. Uji serah terima: jalankan checklist manual `docs/refactor/04-rencana-uji.md` dengan kamera dan mikroskop di lokasi.
4. Berita acara serah terima: [ISI: format, penandatangan]

## 3. Pelatihan pengguna

| Peran | Materi | Durasi | Pelatih |
|---|---|---|---|
| Laboran | Sesi pasien, fokus, ambil dan simpan citra, analisis | [ISI] | [ISI] |
| Dokter | Review sel, kesimpulan skrining, laporan | [ISI] | [ISI] |
| Pengelola perangkat | Pembaruan, cadangan, troubleshooting | [ISI] | [ISI] |

Bahan: panduan pengguna (`docs/panduan-aplikasi.md`/`.pdf`), [ISI: video, kartu ringkas di meja mikroskop].

## 4. Pembaruan aplikasi

- Rilis menggunakan tag versi (lihat `CHANGELOG.md`). Perangkat lapangan hanya menjalankan versi yang sudah lulus checklist manual.
- Cara memperbarui tanpa internet: [ISI: mis. flashdisk berisi paket rilis + skrip pasang]
- Rollback: `git checkout vX.Y.Z` atau paket rilis sebelumnya. Data pasien tidak terpengaruh.
- Pembaruan model: [ISI: cara mengirim bobot model baru, validasi sebelum dipakai]

## 5. Data pasien

- Lokasi penyimpanan di perangkat: [ISI: folder, mis. `/media/ssd/apusan/<tanggal>/`]
- Identitas: ID pasien (sementara). Pemetaan ID ke identitas asli disimpan [ISI: di luar aplikasi, oleh siapa].
- Persetujuan pasien (informed consent) untuk pemakaian data riset: [ISI]
- Akses: [ISI: login/PIN per pengguna atau tidak]
- Enkripsi penyimpanan dan paket review jarak jauh: [ISI]
- Masa simpan dan penghapusan: [ISI]

## 6. Cadangan data

- Jadwal: [ISI: harian/mingguan]
- Media: [ISI: hard disk eksternal, unggah saat ada internet]
- Penanggung jawab: [ISI]
- Uji pemulihan: [ISI: seberapa sering cadangan dicoba dipulihkan]

## 7. Pengiriman data ke tim riset

- Isi kiriman: citra, `capture_log.csv`, `segmentation_log.csv`, JSON hasil review, export COCO.
- Cara dan jadwal: [ISI]
- Anonimisasi sebelum dikirim: [ISI]

## 8. Dukungan dan troubleshooting

- Kontak dukungan: [ISI]
- Masalah umum: [ISI: kamera tidak terdeteksi, penyimpanan penuh, layar sentuh tidak responsif]
- Pencatatan insiden: [ISI: formulir/log]

## 9. Kepatuhan dan validasi

Lihat `use-case.md` bagian 6. Daftar dokumen yang mungkin dibutuhkan: [ISI: protokol validasi klinis, persetujuan etik, izin edar, analisis risiko].
