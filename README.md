> **Panduan pengguna:** [versi Markdown](docs/panduan-aplikasi.md) · [versi PDF](docs/panduan-aplikasi.pdf)

# Aplikasi Akuisisi Citra Apusan Darah Tepi (ADT)

Aplikasi web lokal untuk akuisisi citra apusan darah tepi dari kamera mikroskop USB.

## Persyaratan

Aplikasi ini bisa jalan di **Windows** atau **Ubuntu/Linux**.

### Windows

- Python 3.9+. Jika belum, download dari [python.org](https://www.python.org/downloads/windows/) dan centang opsi **Add Python to PATH** saat install.
- Kamera mikroskop USB dengan driver **DirectShow** sudah terpasang (untuk kamera MiiCam: install `MIIDshowSetup.exe` dari [situs resmi](https://miicamera.net/)).

### Ubuntu/Linux

- Python 3.9+ (biasanya sudah ada bawaan). Cek dengan `python3 --version`.
- Paket sistem tambahan:
  ```
  sudo apt update
  sudo apt install python3-venv python3-tk v4l-utils
  ```
  `python3-tk` dibutuhkan buat dialog pilih folder, `v4l-utils` buat cek kamera (`v4l2-ctl --list-devices`).
- Kamera mikroskop USB: kalau kameranya UVC-compliant, Ubuntu biasanya langsung mendeteksinya lewat driver V4L2 bawaan kernel -- tidak perlu install driver tambahan seperti di Windows. Colok kameranya, lalu cek dengan `v4l2-ctl --list-devices` atau `ls /dev/video*` untuk pastikan sudah terbaca.
- **Kamera MiiCam khususnya** ternyata tidak selalu bisa di-bind driver kernel `uvcvideo` standar di semua board (mis. NVIDIA Jetson) -- aplikasi ini otomatis fallback pakai **SDK vendor ToupCam** kalau itu terjadi. SDK ini dibundel per-arsitektur CPU di `vendor/toupcam/<arch>/` (`arm64/` untuk Jetson, `x64/` untuk Ubuntu x86_64 biasa) dan arsitekturnya **dideteksi otomatis** (`platform.machine()`), jadi tidak perlu ganti file manual pindah board. SDK ini butuh udev rule supaya bisa diakses tanpa root; `run.sh` akan menawarkan install otomatis, atau manual:
  ```
  sudo cp vendor/toupcam/99-toupcam.rules /etc/udev/rules.d/
  sudo udevadm control --reload-rules && sudo udevadm trigger
  ```
  Lalu cabut-colok ulang kameranya.

## Cara menjalankan

### Windows -- Otomatis (disarankan)

Double-click **`run.bat`**. Skrip ini otomatis:
1. Mengecek Python terinstall
2. Membuat virtual environment (`venv`) kalau belum ada
3. Menginstall/memperbarui library dari `requirements.txt`
4. Menjalankan server dan membuka browser ke `http://127.0.0.1:5000`

Untuk menghentikan aplikasi, tutup jendela hitam berjudul "ThalassemiaWebApp - Server".

### Windows -- Manual

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Lalu buka `http://127.0.0.1:5000` di browser.

### Ubuntu/Linux -- Otomatis (disarankan)

```
chmod +x run.sh   # cuma perlu sekali
./run.sh
```
Skrip ini otomatis bikin venv, install/update dependency, jalankan server, dan buka browser ke `http://127.0.0.1:5000`. Tekan `Ctrl+C` di terminal buat menghentikan.

### Ubuntu/Linux -- Manual

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```
Lalu buka `http://127.0.0.1:5000` di browser.

## Alur pemakaian

1. Colokkan kamera mikroskop USB, pastikan sudah terbaca sistem operasi (Windows: cek Device Manager. Ubuntu/Linux: cek `v4l2-ctl --list-devices` atau `ls /dev/video*`).
2. Di TopBar, pilih nama kamera yang benar di dropdown. Atur juga resolusi bila perlu (opsional sebab "Bawaan kamera" pakai resolusi maksimal default), lalu klik **Hubungkan**. Resolusi aktual yang benar-benar dipakai kamera ditampilkan di sebelah status "Aktif". Kalau kameranya mendukung, resolusi diatur langsung di kamera; kalau tidak, gambar akan otomatis diperkecil sesuai pilihan ini saat proses **Save** (FOV tetap penuh, cuma di-scale down, bukan di-crop).
3. Isi **Inisial/ID Pasien**.
4. Klik **Capture** untuk mengambil gambar diam dari stream. Tinjau hasilnya di panel "Hasil Capture".
5. Kalau belum pas, klik Capture lagi buat mengambil ulang.
6. Klik **Lokasi Simpan** untuk memilih folder tujuan (dialog folder native akan muncul). Panel **Ringkasan Folder** otomatis muncul dan menampilkan jumlah gambar per pasien di folder tersebut.
7. Klik **Save**. File tersimpan dengan format `id-pasien_YYYYMMDD-HHMMSS_NN.png`, dan Ringkasan Folder ikut ter-update otomatis. Metadata capture (timestamp, id pasien, filename, iterasi, kamera, resolusi, skor fokus) juga dicatat ke `capture_log.csv` di folder yang sama.
8. Gambar yang berhasil disimpan pada sesi ini juga muncul di galeri riwayat di bagian bawah halaman. **Klik thumbnail untuk preview** gambar besar dengan ringkasan badge kualitas saat disimpan (fokus, pinggir, CLIP). Di dalam preview: klik gambar untuk zoom 100% (berguna memeriksa pojok/pinggir), tombol **Sebelumnya/Berikutnya** atau panah kiri/kanan untuk pindah gambar, **Esc** atau klik area gelap untuk menutup. Selama preview terbuka, Spasi dan Enter tidak memicu Capture/Save. Yang dipreview adalah hasil capture dalam resolusi asli kamera, bukan versi yang diperkecil oleh pilihan resolusi saat Save.

## Kualitas fokus seluruh frame

Di bawah panel Stream ada kartu **Kualitas Fokus (seluruh frame)**. Dokter menganotasi citra penuh, jadi yang dinilai seluruh frame termasuk pinggir, bukan hanya tengah. Metodenya Tenengrad per tile (grid 8x6) yang hasilnya dibandingkan dengan **puncak tile itu sendiri**, karena nilai mentahnya sangat bergantung pada isi gambar (sel padat vs jarang) dan tidak bisa dibandingkan antar lapang pandang. Variance Laplacian (skor lama) tetap dicatat tetapi tidak dipakai untuk menilai, karena sebagian besarnya adalah noise sensor.

**Cara pakai di mikroskop**
1. Letakkan lapang pandang yang akan diambil.
2. Putar fokus **sedikit melewati titik paling tajam, lalu kembali**. Kartu menampilkan "Puncak fokus belum terkonfirmasi" sampai hal ini dilakukan, karena tanpa pembanding tiap frame otomatis jadi puncak baru.
3. Setelah puncak terkonfirmasi, kartu menampilkan status **Baik / Sedang / Buram** dan persen dari puncak. Peta tile: hijau = dekat puncak tile itu, merah = jauh. Tile pinggir yang puncaknya di posisi fokus berbeda (lengkung bidang) tidak dihukum oleh tile tengah.
4. Klik **Capture**. Badge "Fokus ..." di panel Hasil Capture memakai penilaian ini. Kalau statusnya Buram, **Save** meminta konfirmasi dulu (peringatan, bukan pemblokiran).

**Peringatan pinggir lemah.** Status di atas hanya menilai setelan fokus (dekat puncak tiap tile), jadi pinggir yang buram bawaan, misalnya karena preparat atau kamera miring, tidak menurunkannya. Sebagai petunjuk tambahan, kartu dan badge "Pinggir lemah" muncul kalau rasio Tenengrad **tepi/tengah** di bawah `FOCUS_EDGE_RATIO_WARN = 0.65`. Peringatan ini satu-frame (tidak perlu puncak terkonfirmasi) dan **tidak mengubah status**. Ambang 0,65 adalah persentil ke-25 rasio di 80 gambar data 27-08 (menandai sekitar 29% gambar); heuristik, karena sel yang lebih jarang di pinggir juga menurunkan rasio tanpa ada blur. Rasio dan flag-nya dicatat di log (`edge_ratio`, `edge_warn`).

**Perhatikan**
- Referensi puncak **direset otomatis** kalau lapang pandang berganti (citra kasar tidak lagi cocok dengan referensi). Tombol **Reset puncak** untuk reset manual.
- Ambang status (`FOCUS_REL_GOOD = 0.85`, `FOCUS_REL_WARN = 0.65` di `config.py`) **masih heuristik**, belum dikalibrasi dengan label dokter. Yang dicatat ke log adalah nilai mentahnya, supaya ambang bisa dikalibrasi setelah ada penilaian dokter.
- Tile tanpa sel (latar kosong) tidak dihitung. Ambangnya (`FOCUS_TILE_MIN_STD`) berupa perkiraan, karena pada data 27-08 hampir semua tile berisi sel.
- Kartu bisa dimatikan dengan mencentang/mengosongkan **Live** (menghemat CPU; analisis tetap berjalan saat Capture).
- Satu analisis frame 5 MP sekitar 0,1 detik di laptop; di Jetson belum diukur. Kartu memoll tiap ~0,7 detik.

**Kolom tambahan di `capture_log.csv`** (file lama otomatis dimigrasi, baris lama dikosongkan): `tile_median`, `tile_low` (persentil ke-25 tile), `tile_center`, `tile_edge`, `tile_valid_frac`, `rel_low`, `rel_median`, `focus_status`, `tile_map_json` (nilai 6x8 tile), dan `clip_*`. Kolom `focus_score` tetap variance Laplacian lama.

### Skor semantik CLIP (opsional, eksperimen)

Nonaktif secara default. Menghitung skor kepadatan sel (`clip_kepadatan`, `clip_gabungan_v2`, `clip_norm`) dengan 12 crop yang tersebar di seluruh frame, **hanya saat Capture**. Skornya belum divalidasi dengan label dokter: ditampilkan sebagai badge dan dicatat ke log, bukan dipakai sebagai gerbang. Dari eksperimen, sinyalnya terutama kepadatan sel.

```
# Pasang PyTorch sesuai platform dulu (lihat requirements-clip.txt), lalu:
pip install -r requirements-clip.txt

# Windows: double-click run-clip.bat (sama seperti run.bat, dengan CLIP aktif)
# Windows (cmd):   set CLIP_QUALITY=1 && python app.py
# Linux/Jetson:    CLIP_QUALITY=1 python app.py
```

Di laptop pengembangan, venv aplikasi sudah berisi PyTorch versi CPU dan `open_clip_torch` (cukup, sekitar 1 detik per Capture). `run.bat` biasa tetap menjalankan aplikasi tanpa CLIP.

- Bobot model (~600 MB) diunduh dari Hugging Face saat pertama dipakai. **Jalankan sekali dengan internet sebelum ke lab**, setelah itu tersimpan di cache. Model dimuat di latar belakang setelah kamera terhubung; kartu fokus menampilkan status pemuatannya.
- Model bisa diganti lewat `CLIP_MODEL` dan `CLIP_PRETRAINED`. Default `ViT-B-32` / `openai` sama dengan yang diuji di eksperimen. Open_clip memperingatkan mismatch QuickGELU untuk kombinasi ini; `ViT-B-32-quickgelu` belum diuji.

## Struktur folder

```
thalassemia-capture-app/
├── app.py                 # Membuat app Flask, mendaftarkan blueprint, halaman utama
├── config.py              # Konstanta dan env var (ambang fokus, CLIP, daftar kelas, nama log)
├── csvlog.py              # Lock global dan penulisan capture_log.csv / segmentation_log.csv
├── quality.py             # Kualitas fokus per tile, FocusTracker, skor CLIP opsional
├── camera.py              # Kamera (OpenCV/ToupCam) dan stream MJPEG
├── capture.py             # Route kamera, capture, fokus, pilih folder, simpan
├── utils.py               # Helper bersama (safe_slug, frame_to_png_base64)
├── segmentation/          # Tab Segmentasi
│   ├── __init__.py         # Blueprint segmentation_bp
│   ├── mock_model.py       # Model DUMMY (deteksi acak), nanti diganti model asli
│   ├── storage.py          # Baca hasil tersimpan dan konfigurasi model
│   ├── routes.py           # Route run/load/list/save/batch/ringkasan/model
│   └── export.py           # Export laporan Excel dan dataset COCO
├── tests/                 # Tes karakterisasi (python -m unittest discover -s tests)
├── requirements.txt
├── run.bat                 # Runner otomatis untuk Windows
├── run.sh                  # Runner otomatis untuk Ubuntu/Linux
├── check_cameras.py        # Skrip diagnostik kamera (opsional, buat debug)
├── vendor/
│   └── toupcam/             # SDK vendor ToupCam -- fallback kalau uvcvideo gagal bind
│       ├── arm64/            # untuk NVIDIA Jetson dkk
│       │   ├── toupcam.py
│       │   └── libtoupcam.so
│       ├── x64/              # untuk Ubuntu x86_64 biasa
│       │   ├── toupcam.py
│       │   └── libtoupcam.so
│       └── 99-toupcam.rules  # udev rule, arsitektur-independen
├── templates/
│   └── index.html
└── static/
    ├── css/style.css          # tema terang/gelap, tata letak dua layar
    ├── fonts/                 # Atkinson Hyperlegible (OFL), tanpa CDN
    └── js/
        ├── common.js          # toast, modal, tema, pindah layar
        ├── capture.js         # layar Akuisisi
        ├── segmentation.js    # layar Analisis sel
        └── main.js            # event dan inisialisasi (dimuat terakhir)
```

## Troubleshooting

**Ubuntu: `venv/bin/activate: No such file or directory`**
- Biasanya karena paket `python3-venv` belum terinstall, jadi `python3 -m venv venv` gagal separuh jalan. Install: `sudo apt update && sudo apt install python3-venv` (sesuaikan versi Python kamu, mis. `python3.11-venv` -- cek dengan `python3 --version`), lalu jalankan lagi `./run.sh` (skrip otomatis bikin ulang venv yang rusak).

**Kamera tidak muncul di dropdown**
- Windows: pastikan driver DirectShow kamera sudah terinstall. Cek juga di Device Manager apakah kamera memang terbaca di level Windows.
- Ubuntu/Linux: cek `v4l2-ctl --list-devices` -- kalau kamera tidak muncul di situ juga, berarti belum terbaca di level sistem (coba kabel/port USB lain).
- Tutup aplikasi lain yang mungkin sedang memakai kamera yang sama (OBS Studio, aplikasi viewer bawaan kamera, dll), kamera USB umumnya cuma bisa dipakai satu aplikasi dalam satu waktu.
- Kalau masih bermasalah, jalankan `python check_cameras.py` (dengan venv aktif) buat lihat detail index & status buka tiap kamera, lalu cek pesan errornya.

**Gambar hasil capture semua identik (duplikat)**
- Biasanya karena panel Stream sempat tidak aktif/ter-render (misal tab browser di-minimize) sehingga video freeze di satu frame. Pastikan panel Stream kelihatan bergerak sebelum melakukan capture.

**Ubuntu: `ImportError: libGL.so.1: cannot open shared object file`**
- Kurang library sistem yang dibutuhkan OpenCV. Install: `sudo apt install libgl1`.

**Ubuntu: dialog "Lokasi Simpan" tidak muncul / error terkait `tkinter`**
- Paket `python3-tk` belum terinstall: `sudo apt install python3-tk`, lalu jalankan ulang `run.sh`/`python app.py`.

**Ubuntu: kamera tidak bisa dibuka meski muncul di `v4l2-ctl --list-devices` (Permission denied)**
- User belum masuk grup `video`: `sudo usermod -aG video $USER`, lalu logout/login ulang.

**Ubuntu/Jetson: MiiCam kebaca di `lsusb` tapi tidak muncul di `v4l2-ctl --list-devices`**
- Ini kasus yang butuh SDK vendor ToupCam (lihat bagian Persyaratan di atas). Aplikasi otomatis coba backend ini duluan sebelum fallback ke V4L2 -- kalau kamera tetap tidak muncul di dropdown aplikasi, cek:
  1. Udev rule sudah terinstall (`ls /etc/udev/rules.d/99-toupcam.rules`) dan kamera sudah dicabut-colok ulang setelahnya.
  2. Konsol server (`python app.py`) menampilkan baris `[DEBUG] ToupCam EnumV2 gagal: ...` atau `[DEBUG] ToupCam SDK gagal dimuat: ...` -- pesan errornya biasanya menunjukkan penyebabnya (mis. `libtoupcam.so` tidak ditemukan).
  3. Untuk arsitektur CPU selain arm64/x64 (belum dibundel), tambahkan folder baru `vendor/toupcam/<arch>/` berisi `toupcam.py` + `libtoupcam.so` yang sesuai dari ToupCamSDK, lalu daftarkan di `_TOUPCAM_ARCH_MAP` pada `camera.py`.
