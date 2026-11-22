"""Bandingkan preprocessing (crop tengah, unsharp mask, CLAHE) pada gambar hasil capture.

Skrip ini hanya untuk eksplorasi: gambar asli tidak diubah, hasil ditulis ke folder output.

Contoh:
    python preprocess_compare.py "D:/.../Data fix/27-08/pasien-1" --n 3
    python preprocess_compare.py path/ke/folder --crop 0.6 --amount 1.2 --clip 2.0

Per gambar dihasilkan dua file di folder output:
  <nama>_overview.jpg : semua varian berdampingan (diperkecil)
  <nama>_edge.png     : potongan pojok kiri atas resolusi asli (area yang paling buram)
"""
import argparse
import glob
import os

import cv2
import numpy as np


def center_crop(img, frac):
    """Crop tengah dengan rasio aspek sama; frac = fraksi sisi (0.65 = 65%)."""
    h, w = img.shape[:2]
    ch, cw = int(h * frac), int(w * frac)
    y0, x0 = (h - ch) // 2, (w - cw) // 2
    return img[y0:y0 + ch, x0:x0 + cw]


def unsharp(img, sigma, amount):
    """Unsharp mask: img + amount * (img - blur)."""
    blur = cv2.GaussianBlur(img, (0, 0), sigma)
    return cv2.addWeighted(img, 1.0 + amount, blur, -amount, 0)


def clahe(img, clip, tiles):
    """CLAHE pada kanal L (LAB) supaya warna tidak bergeser."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=clip, tileGridSize=(tiles, tiles)).apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def label(img, text):
    out = img.copy()
    cv2.rectangle(out, (0, 0), (out.shape[1], 34), (0, 0, 0), -1)
    cv2.putText(out, text, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return out


def tile(img, height):
    scale = height / img.shape[0]
    return cv2.resize(img, (int(img.shape[1] * scale), height), interpolation=cv2.INTER_AREA)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="folder berisi gambar (png/jpg)")
    ap.add_argument("--out", default="preproc_compare_out", help="folder output")
    ap.add_argument("--n", type=int, default=3, help="jumlah gambar yang diambil merata dari folder")
    ap.add_argument("--crop", type=float, default=0.65, help="fraksi sisi untuk crop tengah")
    ap.add_argument("--sigma", type=float, default=2.0, help="sigma Gaussian untuk unsharp mask")
    ap.add_argument("--amount", type=float, default=1.0, help="kekuatan unsharp mask")
    ap.add_argument("--clip", type=float, default=2.0, help="clipLimit CLAHE")
    ap.add_argument("--tiles", type=int, default=8, help="jumlah tile CLAHE per sisi")
    ap.add_argument("--tile-height", type=int, default=600, help="tinggi tiap panel di overview")
    args = ap.parse_args()

    files = sorted(
        f for ext in ("*.png", "*.jpg", "*.jpeg") for f in glob.glob(os.path.join(args.folder, ext))
    )
    if not files:
        raise SystemExit(f"Tidak ada gambar di {args.folder}")
    idx = np.linspace(0, len(files) - 1, min(args.n, len(files))).round().astype(int)
    os.makedirs(args.out, exist_ok=True)

    for i in sorted(set(idx)):
        path = files[i]
        name = os.path.splitext(os.path.basename(path))[0]
        img = cv2.imread(path)
        if img is None:
            print("Gagal baca:", path)
            continue

        variants = {
            "asli": img,
            f"crop {int(args.crop * 100)}%": center_crop(img, args.crop),
            f"unsharp s={args.sigma} a={args.amount}": unsharp(img, args.sigma, args.amount),
            f"CLAHE clip={args.clip}": clahe(img, args.clip, args.tiles),
            "crop+unsharp+CLAHE": clahe(unsharp(center_crop(img, args.crop), args.sigma, args.amount), args.clip, args.tiles),
        }

        overview = np.hstack([label(tile(v, args.tile_height), k) for k, v in variants.items()])
        cv2.imwrite(os.path.join(args.out, f"{name}_overview.jpg"), overview, [cv2.IMWRITE_JPEG_QUALITY, 92])

        # Pojok kiri atas resolusi asli (crop tengah tidak punya pojok itu, jadi pakai gambar asli sebagai dasar)
        ph, pw = 500, 640
        edge_variants = {
            "asli": img,
            f"unsharp s={args.sigma} a={args.amount}": variants[f"unsharp s={args.sigma} a={args.amount}"],
            f"CLAHE clip={args.clip}": variants[f"CLAHE clip={args.clip}"],
            "unsharp+CLAHE": clahe(unsharp(img, args.sigma, args.amount), args.clip, args.tiles),
        }
        edge = np.hstack([label(v[:ph, :pw], k) for k, v in edge_variants.items()])
        cv2.imwrite(os.path.join(args.out, f"{name}_edge.png"), edge)
        print("OK:", name)

    print("Hasil di:", os.path.abspath(args.out))


if __name__ == "__main__":
    main()
