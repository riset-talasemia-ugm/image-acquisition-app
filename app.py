"""
Thalassemia WebApp - Image Acquisition App
Jalankan:
    pip install -r requirements.txt
    python app.py
Lalu buka http://127.0.0.1:5000 di browser.

Isi aplikasi ada di modul lain:
    config.py        konstanta dan env var
    csvlog.py        lock global dan penulisan log CSV
    quality.py       kualitas fokus per tile dan skor CLIP opsional
    camera.py        kamera (OpenCV/ToupCam) dan stream MJPEG
    capture.py       blueprint capture_bp: kamera, capture, fokus, simpan
    utils.py         helper bersama (safe_slug, frame_to_png_base64)
    segmentation/    blueprint segmentation_bp: segmentasi, export, konfigurasi model
    rating.py        blueprint rating_bp: lembar penilaian citra oleh dokter (F14)
    autocapture.py   gerbang capture otomatis tingkat 1 (UC-13)
    report.py        blueprint report_bp: laporan pasien siap cetak/PDF (UC-07)
"""

import os

from flask import Flask, render_template

from capture import capture_bp
from rating import rating_bp
from report import report_bp
from segmentation import segmentation_bp

app = Flask(__name__)
app.register_blueprint(capture_bp)
app.register_blueprint(segmentation_bp)
app.register_blueprint(rating_bp)
app.register_blueprint(report_bp)


# ---------------------------------------------------------------------------
# Routes - halaman
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    # Dialog "Pengaturan Driver" cuma didukung Windows+DirectShow -- dipakai
    # template buat sembunyikan tombolnya di OS lain (Linux/toupcam) daripada
    # nampilin tombol yang kalau diklik cuma keluar toast "tidak didukung".
    return render_template("index.html", is_windows=(os.name == "nt"))


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
