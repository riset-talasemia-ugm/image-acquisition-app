"""Kualitas citra: fokus per tile (Tenengrad relatif puncak), skor CLIP opsional, deteksi frame kosong."""

import math
import threading

import cv2
import numpy as np

from config import (
    BLANK_STD_THRESHOLD,
    CLIP_CROP_FRAC,
    CLIP_ENABLED,
    CLIP_GRID_COLS,
    CLIP_GRID_ROWS,
    CLIP_MODEL_NAME,
    CLIP_PRETRAINED,
    FOCUS_EDGE_RATIO_WARN,
    FOCUS_FIELD_CHANGE_NCC,
    FOCUS_LOW_PERCENTILE,
    FOCUS_PEAK_DROP,
    FOCUS_PEAK_TOL,
    FOCUS_REL_GOOD,
    FOCUS_REL_WARN,
    FOCUS_TILE_COLS,
    FOCUS_TILE_MIN_STD,
    FOCUS_TILE_ROWS,
    _CLIP_DENSITY_PAIR,
    _CLIP_NEG_V2,
    _CLIP_POS_V2,
)


def compute_focus_score(frame):
    """Estimasi ketajaman fokus."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def compute_focus_tiles(frame):
    """Tenengrad per tile di seluruh frame.

    Gradien dihitung sekali di frame penuh (setelah Gaussian 5x5) lalu
    dirata-rata per tile lewat resize INTER_AREA, jadi tidak ada artefak di
    batas tile. Mengembalikan (teng, valid, small): matriks (ROWS, COLS) nilai
    Tenengrad, mask tile yang berisi sel (bukan latar kosong), dan citra abu-abu
    kasar 64x48 untuk mendeteksi pindah lapang pandang.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    blurred = cv2.GaussianBlur(gray, (5, 5), 1.0)
    grad = (
        cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3) ** 2
        + cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3) ** 2
    )
    size = (FOCUS_TILE_COLS, FOCUS_TILE_ROWS)
    teng = cv2.resize(grad, size, interpolation=cv2.INTER_AREA)
    mean = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
    mean_sq = cv2.resize(gray * gray, size, interpolation=cv2.INTER_AREA)
    std = np.sqrt(np.maximum(mean_sq - mean * mean, 0.0))
    small = cv2.resize(gray, (64, 48), interpolation=cv2.INTER_AREA)
    return teng, std >= FOCUS_TILE_MIN_STD, small


def _ncc(a, b):
    """Normalized cross-correlation dua citra kasar (1 = identik)."""
    a = a - a.mean()
    b = b - b.mean()
    denom = math.sqrt(float((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / denom) if denom > 1e-6 else 1.0


class FocusTracker:
    """Peak-hold Tenengrad per tile untuk lapang pandang yang sedang diamati.

    Selama operator memutar fokus, tiap tile mengingat nilai tertingginya; skor
    relatif = nilai sekarang / puncak tile itu. Karena tile yang sama
    dibandingkan dengan dirinya sendiri, pengaruh isi gambar (padat/jarang)
    hilang, dan tile pinggir yang puncaknya di posisi fokus berbeda (lengkung
    bidang) tidak dihukum oleh tile tengah.

    Otomatis reset kalau lapang pandang berganti (citra kasar tidak lagi
    berkorelasi dengan referensi).
    """

    def __init__(self):
        self.lock = threading.Lock()
        self._reset_locked()

    def _reset_locked(self):
        self.peak = None
        self.ref_small = None
        self.med_peak = None      # median Tenengrad tertinggi yang teramati
        self.dropped = False      # sudah turun >= FOCUS_PEAK_DROP setelah puncak itu?

    def reset(self):
        with self.lock:
            self._reset_locked()

    def update(self, teng, valid, small):
        """Return (usable, rel, confirmed, changed)."""
        with self.lock:
            changed = False
            if self.ref_small is not None and _ncc(self.ref_small, small) < FOCUS_FIELD_CHANGE_NCC:
                self._reset_locked()
                changed = True
            if self.ref_small is None:
                self.ref_small = small

            current = np.where(valid, teng, 0.0)
            self.peak = current.copy() if self.peak is None else np.maximum(self.peak, current)

            if valid.any():
                med = float(np.median(teng[valid]))
                if self.med_peak is None or med > self.med_peak * (1.0 + FOCUS_PEAK_TOL):
                    self.med_peak = med          # puncak baru -> konfirmasi diulang
                    self.dropped = False
                else:
                    self.med_peak = max(self.med_peak, med)   # naik tipis = noise
                    if med <= self.med_peak * FOCUS_PEAK_DROP:
                        self.dropped = True
            confirmed = bool(self.dropped)

            usable = valid & (self.peak > 0)
            rel = np.zeros(teng.shape, dtype=np.float32)
            rel[usable] = np.minimum(teng[usable] / self.peak[usable], 1.0)
            return usable, rel, confirmed, changed


focus_tracker = FocusTracker()


def focus_status(rel_low, confirmed):
    """'baik' / 'sedang' / 'buram', atau None kalau puncak belum terkonfirmasi."""
    if not confirmed or rel_low is None:
        return None
    if rel_low >= FOCUS_REL_GOOD:
        return "baik"
    if rel_low >= FOCUS_REL_WARN:
        return "sedang"
    return "buram"


def analyze_focus(frame):
    """Analisis fokus seluruh frame + update peak-hold. Hasilnya dict siap-JSON."""
    teng, valid, small = compute_focus_tiles(frame)
    rows, cols = teng.shape
    result = {"valid": bool(valid.any()), "rows": rows, "cols": cols}
    if not valid.any():
        return result

    ring = np.zeros(teng.shape, dtype=bool)
    ring[0, :] = ring[-1, :] = True
    ring[:, 0] = ring[:, -1] = True
    inner, outer = valid & ~ring, valid & ring
    center = float(teng[inner].mean()) if inner.any() else None
    edge = float(teng[outer].mean()) if outer.any() else None

    usable, rel, confirmed, changed = focus_tracker.update(teng, valid, small)
    rel_vals = rel[usable]
    rel_low = float(np.percentile(rel_vals, FOCUS_LOW_PERCENTILE)) if rel_vals.size else None
    rel_median = float(np.median(rel_vals)) if rel_vals.size else None

    vals = teng[valid]
    edge_ratio = (edge / center) if (center and edge is not None) else None
    result.update({
        "median": float(np.median(vals)),
        "low": float(np.percentile(vals, FOCUS_LOW_PERCENTILE)),
        "center": center,
        "edge": edge,
        "edgeRatio": edge_ratio,
        "edgeWarn": bool(edge_ratio is not None and edge_ratio < FOCUS_EDGE_RATIO_WARN),
        "validFrac": float(valid.mean()),
        "relLow": rel_low,
        "relMedian": rel_median,
        "confirmed": confirmed,
        "changed": changed,
        "status": focus_status(rel_low, confirmed),
        "tiles": [
            [round(float(teng[r, c]), 1) if valid[r, c] else None for c in range(cols)]
            for r in range(rows)
        ],
        "tilesRel": [
            [round(float(rel[r, c]), 3) if usable[r, c] else None for c in range(cols)]
            for r in range(rows)
        ],
    })
    return result


def analyze_focus_safe(frame):
    """Capture/Save tidak boleh gagal hanya karena analisis kualitas error."""
    try:
        return analyze_focus(frame)
    except Exception as e:
        print(f"[DEBUG] analyze_focus gagal: {e}")
        return {"valid": False, "error": str(e)}


class ClipQuality:
    """Skor semantik CLIP (kepadatan sel), opsional dan dimuat malas.

    Nonaktif kecuali CLIP_QUALITY=1. Model dimuat di thread latar pada request
    pertama supaya tidak menahan startup dan aman terhadap reloader Flask
    debug. Hanya encoder gambar yang jalan per Capture; embedding teks
    dihitung sekali saat model dimuat.
    """

    def __init__(self):
        self.state = "idle" if CLIP_ENABLED else "disabled"
        self.error = None
        self._state_lock = threading.Lock()
        self._infer_lock = threading.Lock()

    def ensure_started(self):
        with self._state_lock:
            if self.state != "idle":
                return
            self.state = "loading"
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            import torch
            import open_clip

            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, _, preprocess = open_clip.create_model_and_transforms(
                CLIP_MODEL_NAME, pretrained=CLIP_PRETRAINED, device=device
            )
            model.eval()
            tokenizer = open_clip.get_tokenizer(CLIP_MODEL_NAME)
            norm = [t for t in preprocess.transforms if t.__class__.__name__ == "Normalize"][0]
            size = model.visual.image_size
            size = int(size[0] if isinstance(size, (tuple, list)) else size)

            def encode_text(prompts):
                with torch.no_grad():
                    t = model.encode_text(tokenizer(prompts).to(device)).float()
                return t / t.norm(dim=-1, keepdim=True)

            def class_vec(prompts):
                v = encode_text(prompts).mean(0)
                return v / v.norm()

            self._text = {
                "kepadatan": encode_text(list(_CLIP_DENSITY_PAIR)),                       # (2, D)
                "gabungan_v2": torch.stack([class_vec(_CLIP_POS_V2), class_vec(_CLIP_NEG_V2)]),
            }
            self._torch = torch
            self._model = model
            self._device = device
            self._size = size
            self._mean = torch.tensor(norm.mean, device=device).view(1, 3, 1, 1)
            self._std = torch.tensor(norm.std, device=device).view(1, 3, 1, 1)
            self._logit_scale = float(model.logit_scale.exp().item())
            self.state = "ready"
            print(f"[DEBUG] CLIP siap: {CLIP_MODEL_NAME}/{CLIP_PRETRAINED} di {device}")
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            self.state = "error"
            print(f"[DEBUG] CLIP gagal dimuat: {self.error}")

    def score(self, frame_bgr):
        """dict skor rata-rata semua crop, atau None kalau belum siap/gagal."""
        if self.state != "ready":
            return None
        try:
            torch = self._torch
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            crop = max(32, min(int(round(w * CLIP_CROP_FRAC)), h, w))
            ys = np.linspace(0, h - crop, CLIP_GRID_ROWS).astype(int)
            xs = np.linspace(0, w - crop, CLIP_GRID_COLS).astype(int)
            patches = [
                cv2.resize(rgb[y:y + crop, x:x + crop], (self._size, self._size), interpolation=cv2.INTER_AREA)
                for y in ys for x in xs
            ]
            with self._infer_lock:
                x = torch.from_numpy(np.stack(patches)).to(self._device).permute(0, 3, 1, 2).float() / 255
                x = (x - self._mean) / self._std
                with torch.no_grad(), torch.autocast(
                    device_type=self._device, dtype=torch.float16, enabled=(self._device == "cuda")
                ):
                    feats = self._model.encode_image(x)
                feats = feats.float()
                norms = feats.norm(dim=-1)
                unit = feats / norms.unsqueeze(-1)
                out = {
                    "model": f"{CLIP_MODEL_NAME}/{CLIP_PRETRAINED}",
                    "crops": len(patches),
                    "norm": float(norms.mean()),
                }
                for name, text in self._text.items():
                    out[name] = float((self._logit_scale * unit @ text.T).softmax(-1)[:, 0].mean())
            return out
        except Exception as e:
            print(f"[DEBUG] CLIP score gagal: {e}")
            return None


clip_quality = ClipQuality()


def is_blank_frame(frame):
    """Deteksi kasar frame yang kemungkinan kosong/lensa tertutup"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(gray.std()) < BLANK_STD_THRESHOLD
