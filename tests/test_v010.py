"""Tes karakterisasi: mengunci perilaku v0.1.0 supaya refactor tidak mengubahnya.

Jalankan dari root proyek:
    python -m unittest discover -s tests -v

Nilai acuan direkam SEKALI di tag v0.1.0 ke tests/expected_v0.1.0.json:
    RECORD_EXPECTED=1 python -m unittest discover -s tests      (Linux)
    set RECORD_EXPECTED=1 && python -m unittest discover -s tests  (Windows cmd)
Setelah itu file acuan tidak boleh diubah selama refactor (lihat docs/refactor/04-rencana-uji.md).

Semua keluaran tes ditulis ke tmp/test-run/ (bukan folder temp sistem).
Data pasien asli opsional di tmp/data-uji/ (tidak di-commit); tes-nya di-skip kalau tidak ada.
"""
import csv
import hashlib
import json
import os
import random
import re
import shutil
import sys
import unittest

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# --- Satu-satunya bagian yang boleh diubah selama refactor: dari mana simbol di-import. ---
from app import app as flask_app  # noqa: E402
from capture import next_iteration_from_folder, resize_for_save  # noqa: E402
from config import RBC_CLASS_LABELS, SEGMENTATION_LOG_FIELDNAMES  # noqa: E402
from csvlog import _ensure_log_columns, log_capture_csv  # noqa: E402
from quality import analyze_focus, is_blank_frame  # noqa: E402
from utils import safe_slug  # noqa: E402
# -----------------------------------------------------------------------------------------

RECORD = os.environ.get("RECORD_EXPECTED", "").strip() == "1"
EXPECTED_PATH = os.path.join(ROOT, "tests", "expected_v0.1.0.json")
RUN_DIR = os.path.join(ROOT, "tmp", "test-run")
DATA_UJI = os.path.join(ROOT, "tmp", "data-uji")

CAPTURE_LOG_FIELDS = [
    "timestamp", "patient_id", "filename", "iterasi", "camera", "resolution", "focus_score",
    "tile_median", "tile_low", "tile_center", "tile_edge", "tile_valid_frac", "edge_ratio",
    "edge_warn", "rel_low", "rel_median", "focus_status", "tile_map_json",
    "clip_kepadatan", "clip_gabungan_v2", "clip_norm", "clip_model",
    # Ditambahkan sesudah v0.1.0 (capture otomatis, UC-13); log lama dimigrasi otomatis.
    "capture_mode",
]

_TS = [
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?"), "<DATETIME>"),
    # Akhiran -N muncul kalau dua file tersimpan di detik yang sama; tergantung waktu, jadi ikut diabaikan.
    (re.compile(r"\d{8}-\d{6}(-\d+)?"), "<TS>"),
]


def normalize(obj, folder):
    """Ganti path folder uji dan timestamp dengan placeholder supaya bisa dibandingkan."""
    if isinstance(obj, dict):
        return {k: normalize(v, folder) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [normalize(v, folder) for v in obj]
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, str):
        for f in {folder, folder.replace("\\", "/"), os.path.normpath(folder)}:
            obj = obj.replace(f, "<DIR>")
        obj = obj.replace("\\", "/")
        for pattern, repl in _TS:
            obj = pattern.sub(repl, obj)
    return obj


class Snapshot:
    """Bandingkan nilai dengan acuan v0.1.0, atau rekam kalau RECORD_EXPECTED=1."""

    def __init__(self, path):
        self.path = path
        self.data = {}
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                self.data = json.load(f)

    def check(self, test, key, value):
        value = json.loads(json.dumps(value))  # samakan tuple->list dsb.
        if RECORD:
            self.data[key] = value
            return
        test.assertIn(key, self.data, f"Acuan '{key}' belum direkam (jalankan dengan RECORD_EXPECTED=1 di v0.1.0)")
        test.assertEqual(self.data[key], value, f"Berbeda dari v0.1.0: {key}")

    def save(self):
        if RECORD:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1, sort_keys=True)


SNAP = Snapshot(EXPECTED_PATH)


def tearDownModule():
    SNAP.save()


def synthetic_smear(blur=0):
    """Gambar sel sintetis deterministik (lingkaran merah muda di latar terang)."""
    rng = np.random.default_rng(0)
    img = np.full((480, 640, 3), (225, 215, 235), np.uint8)
    for _ in range(250):
        cx, cy, r = int(rng.integers(0, 640)), int(rng.integers(0, 480)), int(rng.integers(8, 18))
        cv2.circle(img, (cx, cy), r, (150, 110, 190), -1)
        cv2.circle(img, (cx, cy), max(2, r // 3), (190, 160, 215), -1)
    if blur:
        img = cv2.GaussianBlur(img, (0, 0), blur)
    return img


def sample_detections():
    """Dua sel buatan tangan: satu dikoreksi + dinilai salah, satu dinilai benar."""
    return [
        {"id": 0, "classIndex": 0, "classLabel": "Normal cell", "confidence": 0.9,
         "bbox": [10, 10, 20, 20], "mask": [[10, 10], [30, 10], [30, 30], [10, 30]],
         "doctorVerdict": "correct"},
        {"id": 1, "classIndex": 0, "classLabel": "Normal cell", "confidence": 0.6,
         "correctedClassIndex": 4, "correctedClassLabel": "Target cell",
         "bbox": [50, 50, 10, 10], "mask": [[50, 50], [60, 50], [60, 60], [50, 60]],
         "doctorVerdict": "incorrect"},
    ]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.join(RUN_DIR, self.id().split(".")[-1])
        shutil.rmtree(self.dir, ignore_errors=True)
        os.makedirs(self.dir)
        self.client = flask_app.test_client()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def snap(self, key, value):
        SNAP.check(self, key, normalize(value, self.dir))

    def read_csv(self, name):
        with open(os.path.join(self.dir, name), newline="", encoding="utf-8") as f:
            return list(csv.reader(f))


class TestRoutes(Base):
    def test_route_snapshot(self):  # 2.1
        rules = sorted(
            f"{r.rule} {','.join(sorted(r.methods - {'HEAD', 'OPTIONS'}))}"
            for r in flask_app.url_map.iter_rules()
            if r.endpoint != "static"
        )
        # Rute v0.1.0 tidak boleh hilang atau berubah method. Rute yang ditambahkan
        # sesudahnya harus tercatat di sini (dan di docs/refactor/01, bagian
        # "Perubahan kontrak sesudah v0.1.0"), supaya tidak bertambah diam-diam.
        added = {
            "/api/rating/next POST",
            "/api/rating/submit POST",
            "/api/recovery/capture GET,POST",
            "/api/segmentation/attributes GET,POST",
            "/api/segmentation/export-comparison POST",
            "/api/segmentation/open-path POST",
            "/api/system/status GET",
            "/laporan GET",
        }
        self.assertEqual(added - set(rules), set(), "rute tambahan tercatat tapi tidak ada")
        self.snap("routes", [r for r in rules if r not in added])


class TestHelpers(Base):
    def test_safe_slug(self):  # 2.2
        cases = ["Budi Santoso", "  AB-12 ", "pasien_01", "ÄÖ!!", "", "X y Z"]
        self.snap("safe_slug", {c: safe_slug(c) for c in cases})

    def test_next_iteration(self):
        self.assertEqual(next_iteration_from_folder(self.dir, "ab"), 1)
        for name in ["ab_20260101-120000_01.png", "ab_20260101-120001_07.png",
                     "abc_20260101-120000_09.png", "ab_x_01.png", "AB_20260101-120000_03.PNG"]:
            open(os.path.join(self.dir, name), "wb").close()
        self.assertEqual(next_iteration_from_folder(self.dir, "ab"), 8)
        self.assertEqual(next_iteration_from_folder(self.dir, "abc"), 10)
        self.assertEqual(next_iteration_from_folder(os.path.join(self.dir, "tidak-ada"), "ab"), 1)

    def test_resize_for_save(self):
        frame = np.zeros((1944, 2592, 3), np.uint8)
        self.assertIs(resize_for_save(frame, None, None), frame)
        self.assertIs(resize_for_save(frame, 4000, 3000), frame)
        self.assertEqual(resize_for_save(frame, 1280, 960).shape, (960, 1280, 3))
        self.assertEqual(resize_for_save(frame, 1920, 1920).shape, (1440, 1920, 3))

    def test_is_blank_frame(self):
        self.assertTrue(is_blank_frame(np.zeros((100, 100, 3), np.uint8)))
        self.assertFalse(is_blank_frame(synthetic_smear()))


class TestCsvLogs(Base):
    def test_segmentation_log_migration(self):  # 2.3
        path = os.path.join(self.dir, "segmentation_log.csv")
        old = ["timestamp", "patient_id", "source_image", "detail_file", "total_cells"] + RBC_CLASS_LABELS
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(old)
            w.writerow(["20260101-120000", "ab", "a.png", "a.json", "3"] + ["1"] * len(RBC_CLASS_LABELS))
        _ensure_log_columns(path, SEGMENTATION_LOG_FIELDNAMES)
        rows = self.read_csv("segmentation_log.csv")
        self.snap("segmentation_log_header", rows[0])
        self.assertEqual(dict(zip(rows[0], rows[1]))["patient_id"], "ab")
        self.assertEqual(dict(zip(rows[0], rows[1]))["is_duplicate"], "")
        self.assertEqual(dict(zip(rows[0], rows[1]))["Elliptocyte"], "1")

    def test_capture_log_migration(self):
        path = os.path.join(self.dir, "capture_log.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(CAPTURE_LOG_FIELDS[:7])
            w.writerow(["20260101-120000", "ab", "ab_20260101-120000_01.png", "1", "cam", "2592x1944", "6.1"])
        log_capture_csv(self.dir, {"timestamp": "20260101-120100", "patient_id": "ab", "focus_status": "baik"})
        rows = self.read_csv("capture_log.csv")
        self.assertEqual(rows[0], CAPTURE_LOG_FIELDS)
        self.assertEqual(len(rows), 3)
        self.assertEqual(dict(zip(rows[0], rows[1]))["focus_score"], "6.1")
        self.assertEqual(dict(zip(rows[0], rows[2]))["focus_status"], "baik")


class TestFocus(Base):
    def test_focus_sequence(self):  # 2.6
        self.assertEqual(self.client.post("/api/focus/reset-peak").status_code, 200)
        results = [analyze_focus(synthetic_smear(b)) for b in (2.0, 0, 1.5, 4.0)]
        self.snap("focus_sequence", results)
        self.client.post("/api/focus/reset-peak")


class TestSegmentation(Base):
    def write_image(self, name="ab_20260101-120000_01.png"):
        path = os.path.join(self.dir, name)
        cv2.imwrite(path, synthetic_smear())
        return path

    def save(self, path, **extra):
        r = self.client.post("/api/segmentation/save", json={
            "path": path, "patientId": "ab", "detections": sample_detections(), **extra})
        self.assertEqual(r.status_code, 200)
        return r.get_json()

    def test_classes(self):
        self.snap("seg_classes", self.client.get("/api/segmentation/classes").get_json())

    def test_mock_run_deterministic(self):  # 2.4 (bagian run)
        path = self.write_image()
        random.seed(7)
        data = self.client.post("/api/segmentation/run", json={"path": path}).get_json()
        dets = data.pop("detections")
        self.assertTrue(all(d["classLabel"] == RBC_CLASS_LABELS[d["classIndex"]] for d in dets))
        digest = hashlib.sha256(json.dumps(dets, sort_keys=True).encode()).hexdigest()
        self.snap("seg_run", {"response": data, "n": len(dets), "sha256": digest})

    def test_save_load_duplicate_summary(self):  # 2.4, 2.8
        path = self.write_image()
        first = self.save(path)
        self.snap("seg_save_first", first)
        with open(first["detailPath"], encoding="utf-8") as f:
            self.snap("seg_detail_json", json.load(f))
        self.snap("seg_log_rows", self.read_csv("segmentation_log.csv"))

        self.snap("seg_save_dup", self.save(path))  # duplikat tanpa force -> minta konfirmasi
        forced = self.save(path, force=True)
        self.snap("seg_save_forced", forced)

        loaded = self.client.post("/api/segmentation/load-path", json={"path": forced["detailPath"]}).get_json()
        self.snap("seg_load_path", loaded)
        q = {"folder": self.dir}
        self.snap("seg_list_results", self.client.get("/api/segmentation/list-results", query_string=q).get_json())
        self.snap("seg_patient_summary", self.client.get("/api/segmentation/patient-summary", query_string=q).get_json())
        self.snap("seg_check_existing", self.client.get(
            "/api/segmentation/check-existing", query_string={"path": path}).get_json())

    def test_exports(self):  # 2.7
        from openpyxl import load_workbook
        path = self.write_image()
        self.save(path)

        rep = self.client.post("/api/segmentation/export-report", json={"folder": self.dir}).get_json()
        self.snap("export_report_response", rep)
        wb = load_workbook(rep["path"])
        # Sheet v0.1.0 harus identik; sheet tambahan sesudahnya tercatat di sini.
        added_sheets = ["Atribut per Pasien", "Koreksi per Sel"]
        self.assertEqual(wb.sheetnames[-len(added_sheets):], added_sheets)
        self.snap("export_report_cells", {ws.title: [list(row) for row in ws.iter_rows(values_only=True)]
                                          for ws in wb.worksheets if ws.title not in added_sheets})
        wb.close()

        for only in (False, True):
            coco = self.client.post("/api/segmentation/export-coco",
                                    json={"folder": self.dir, "onlyReviewed": only}).get_json()
            with open(coco["path"], encoding="utf-8") as f:
                content = json.load(f)
            self.assertEqual([c["name"] for c in content["categories"]], RBC_CLASS_LABELS)
            # Field anotasi tambahan sesudah v0.1.0 (atribut, koreksi dokter) dilepas sebelum dibandingkan.
            for ann in content["annotations"]:
                for key in ("attributes", "attributes_source", "corrected_by_doctor", "added_by_doctor"):
                    ann.pop(key, None)
            self.snap(f"export_coco_onlyReviewed={only}", {"response": coco, "content": content})

    def test_folder_summary(self):  # 2.8
        for name in ["ab_20260101-120000_01.png", "ab_20260101-120001_02.png",
                     "cd_20260101-120000_01.png", "lain.png", "ab_segmentation_x.json"]:
            open(os.path.join(self.dir, name), "wb").close()
        self.snap("folder_summary", self.client.get("/api/folder-summary", query_string={"folder": self.dir}).get_json())


@unittest.skipUnless(os.path.isdir(DATA_UJI), "tmp/data-uji/ tidak ada")
class TestDataLama(unittest.TestCase):  # 2.9
    """Data akuisisi asli (salinan). Acuannya disimpan di tmp/data-uji/, bukan di repo."""

    def test_old_folders(self):
        snap = Snapshot(os.path.join(DATA_UJI, "expected.json"))
        client = flask_app.test_client()
        folders = sorted({os.path.dirname(p) for p in _walk(DATA_UJI, "segmentation_log.csv")})
        for folder in folders:
            rel = os.path.relpath(folder, DATA_UJI)
            for ep in ("list-results", "patient-summary"):
                r = client.get(f"/api/segmentation/{ep}", query_string={"folder": folder})
                self.assertEqual(r.status_code, 200)
                snap.check(self, f"{rel}:{ep}", normalize(r.get_json(), folder))
        for folder in sorted({os.path.dirname(p) for p in _walk(DATA_UJI, ".png")}):
            r = client.get("/api/folder-summary", query_string={"folder": folder})
            snap.check(self, f"{os.path.relpath(folder, DATA_UJI)}:folder-summary", normalize(r.get_json(), folder))
        snap.save()


def _walk(root, suffix):
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.lower().endswith(suffix):
                yield os.path.join(dirpath, f)


if __name__ == "__main__":
    unittest.main()
