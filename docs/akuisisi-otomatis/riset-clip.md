# Ringkasan: CLIP untuk Akuisisi Citra Apusan Darah Tepi (Mikroskop Cerdas, Jetson Orin Nano)

## 1. Kriteria Kualitas Apusan Darah Tepi (Zona Monolayer)
- **Homogen** — sel tersebar merata, distribusi ukuran/bentuk representatif
- **Minim overlap** — eritrosit bersebelahan, tidak bertumpuk
- **Sedikit area kosong** — kepadatan cukup tanpa overlap
- **Fokus tajam**, **warna konsisten**, **bebas artefak** (debu/goresan/gelembung), **pencahayaan merata**

## 2. Struktur Dataset CLIP (2 Level)
| Level | Isi | Caption |
|---|---|---|
| Field image | 1 file = 1 field of view (ratusan sel) | kualitas monolayer (good/blurry/overlap/sparse) |
| Cell patch | crop per sel hasil deteksi/segmentasi dari field | jenis sel (neutrofil, limfosit, dll) |

**Pipeline:**
```
field image → deteksi sel → crop patch → quality filter (CLIP zero-shot)
  → labeling → caption generation → split per patient/slide → dataset CLIP final
```

Split **wajib per patient/slide** (GroupShuffleSplit), bukan per gambar/patch — mencegah data leakage.

Caption dibuat dari template label→deskripsi, idealnya divariasi & divalidasi ahli.

**Isu khusus:** batch CLIP contrastive loss menganggap caption identik sekelas sebagai false negative → mitigasi dengan masking, sampler 1 gambar/kelas per batch, atau caption lebih spesifik.

## 3. Perubahan Konteks: Real-Time Quality Gate saat Akuisisi
Bukan filtering dataset offline — CLIP dipakai sebagai **semantic scorer real-time** saat scanning, menggantikan/melengkapi metrik blur-only yang saat ini dipakai.

**Arsitektur:**
```
capture frame → blur check (cv2 Laplacian, murah) → reject cepat jika gagal
   → lolos → CLIP image encoder → cosine similarity vs text embedding (precomputed)
   → threshold → keep/reject
```

- Text embedding (positive/negative prompt) **di-precompute sekali**, runtime cuma encode gambar
- Kombinasikan CLIP + blur metric (ensemble), jangan gantikan total — blur classic lebih presisi untuk micro-blur
- Threshold dikalibrasi pakai ROC/Youden's J dari data berlabel operator, bukan angka asal tebak

## 4. Deployment di Jetson Orin Nano
- Model CLIP standar (ViT-B/32) terlalu berat → pakai **MobileCLIP** / **TinyCLIP** / ViT-S/16
- Stack: PyTorch/OpenCLIP → **ONNX export** → **TensorRT engine** (FP16, atau INT8 dgn kalibrasi)
- Hanya **image encoder** yang jalan di edge; text encoder & embedding dihitung di luar (precomputed, load statis)
- Cek preprocessing capture (idealnya GPU-accelerated via VPI) — sering jadi bottleneck tersembunyi, bukan modelnya
- Hal yang perlu dicek: JetPack version, varian Orin Nano (4GB/8GB/Super), kompatibilitas TensorRT

## Contoh Prompt CLIP (Quality Scoring)
```python
positive = [
    "a well-spread blood smear with evenly distributed cells",
    "a blood smear with homogeneous cell arrangement and minimal overlap",
    "a monolayer blood smear image with minimal empty space",
]
negative = [
    "a blood smear with heavily overlapping cells",
    "a blood smear with large empty background",
    "a blurry blood smear image",
    "a blood smear with non-uniform sparse cell distribution",
]
```

## Langkah Lanjutan yang Dibahas (belum dieksekusi)
- Deteksi/segmentasi sel per patch
- Fine-tuning / linear probe CLIP dengan data domain spesifik
- Benchmark latency aktual di board Jetson Orin Nano
- Kalibrasi INT8 quantization
