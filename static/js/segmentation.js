// Layar Analisis sel: segmentasi, koreksi, review dokter, export, konfigurasi model.
const segTabSource = document.getElementById("segTabSource");
const segTabResult = document.getElementById("segTabResult");
const segInspector = document.getElementById("segInspector");
const segModelBanner = document.getElementById("segModelBanner");
const statusModel = document.getElementById("statusModel");
const btnSegSelectImage = document.getElementById("btnSegSelectImage");
const btnLoadSegmentation = document.getElementById("btnLoadSegmentation");
const btnRunSegmentation = document.getElementById("btnRunSegmentation");
const btnSaveSegmentation = document.getElementById("btnSaveSegmentation");
const btnSendToSegmentation = document.getElementById("btnSendToSegmentation");
const segPatientNameInput = document.getElementById("segPatientName");
const segImagePathEl = document.getElementById("segImagePath");
const segSourceBody = document.getElementById("segSourceBody");
const segResultBody = document.getElementById("segResultBody");
const segDetectionsBody = document.getElementById("segDetectionsBody");
const classSummaryBody = document.getElementById("classSummaryBody");
const classChartBody = document.getElementById("classChartBody");
const segClassTabTable = document.getElementById("segClassTabTable");
const segClassTabChart = document.getElementById("segClassTabChart");
const btnSegAddCell = document.getElementById("btnSegAddCell");
const btnSegCellShrink = document.getElementById("btnSegCellShrink");
const btnSegCellGrow = document.getElementById("btnSegCellGrow");
const segShowNumbersCheckbox = document.getElementById("segShowNumbersCheckbox");
const btnSegZoomIn = document.getElementById("btnSegZoomIn");
const btnSegZoomOut = document.getElementById("btnSegZoomOut");
const btnSegZoomReset = document.getElementById("btnSegZoomReset");
const segZoomLabel = document.getElementById("segZoomLabel");
const segTotalCellCount = document.getElementById("segTotalCellCount");
const btnSegPatientSummary = document.getElementById("btnSegPatientSummary");
const segPatientSummaryBody = document.getElementById("segPatientSummaryBody");
const btnSegBatchRun = document.getElementById("btnSegBatchRun");
const btnSegListResults = document.getElementById("btnSegListResults");
const segResultsListBody = document.getElementById("segResultsListBody");
const segResultsFilter = document.getElementById("segResultsFilter");
const btnSegExportReport = document.getElementById("btnSegExportReport");
const segCocoOnlyReviewedCheckbox = document.getElementById("segCocoOnlyReviewedCheckbox");
const btnSegExportCoco = document.getElementById("btnSegExportCoco");
const segBulkActionsBar = document.getElementById("segBulkActionsBar");
const segSelectAllCells = document.getElementById("segSelectAllCells");
const segBulkClassSelect = document.getElementById("segBulkClassSelect");
const btnSegBulkApply = document.getElementById("btnSegBulkApply");
const btnSegMarkRestCorrect = document.getElementById("btnSegMarkRestCorrect");
const segModelStatusText = document.getElementById("segModelStatusText");
const segModelPathInput = document.getElementById("segModelPathInput");
const segLowConfidenceThresholdInput = document.getElementById("segLowConfidenceThresholdInput");
const btnSegSaveModelConfig = document.getElementById("btnSegSaveModelConfig");

let segSelectedPath = null; // path gambar sumber yang dipilih di tab Segmentasi
let segCurrentImageDataUrl = null; // data URL gambar sumber yang lagi ditampilkan (buat overlay hasil)
let segDetections = []; // hasil (+ kemungkinan koreksi manual) dari run terakhir
let segClassLabels = []; // cache [{index, label, color}, ...] dari /api/segmentation/classes
let segImgW = 0;
let segImgH = 0;
let segActiveFolder = null; // folder "aktif" buat Ringkasan per Pasien & Muat Daftar -- dari gambar terakhir dipilih/dimuat ATAU folder Proses Batch terakhir
let segActiveCellId = null; // id sel yang lagi dipilih (row diklik / navigasi panah)
let segAddMode = false; // true kalau lagi mode "Tambah Sel Manual"
let segHighlightedClassIndex = null; // kelas yang lagi di-highlight (klik baris/bar di ringkasan kelas)
let segSelectedCellIds = new Set(); // dipakai buat koreksi kelas massal (bulk)
let segResultsListCache = []; // cache hasil terakhir dari list-results, buat filter tanpa fetch ulang
let segShowCellNumbers = true; // toggle label nomor sel di overlay Hasil Segmentasi

// Zoom & pan gambar (Gambar Sumber / Hasil Segmentasi) -- diterapkan lewat
// CSS transform di elemen gambar, jadi koordinat mask (pixel asli gambar)
// nggak perlu diubah sama sekali; konversi klik->pixel pas nambah sel manual
// tetap akurat karena pakai SVG getScreenCTM() yang otomatis memperhitungkan
// transform ini.
let segZoom = 1;
let segPanX = 0;
let segPanY = 0;
let segPanActiveEl = null;
let segDragStartX = 0;
let segDragStartY = 0;
let segMouseDownX = 0;
let segMouseDownY = 0;
let segMouseMoved = false;

// Pecahan 0-1, bukan konstanta -- bisa diatur dari panel "Status Model
// Segmentasi" (lihat loadSegModelStatus/doSaveSegModelConfig), disimpan
// server-side sebagai persen (0-100) di model_config.json.
let segLowConfidenceThreshold = 0.7;

// Batas radius efektif sel saat di-resize (lihat resizeActiveCell) -- biar
// nggak bisa diciutkan sampai nyaris titik atau dibesarkan sampai keluar
// gambar sama sekali.
const MIN_CELL_RADIUS = 4;

// -----------------------------------------------------------------------
// Tab Segmentasi & Klasifikasi Morfologi Sel (scaffold UI -- model deep
// learning-nya belum diintegrasikan, lihat api_segmentation_run di app.py)
// -----------------------------------------------------------------------
async function loadClassLegend() {
  const res = await fetch("/api/segmentation/classes");
  const classes = await res.json();
  if (!Array.isArray(classes)) return; // server terputus
  segClassLabels = classes;
  renderClassSummary(null);
  segBulkClassSelect.innerHTML = segClassLabels
    .map((c) => `<option value="${c.index}">${c.label}</option>`)
    .join("");
}

// counts === null -> tampilan awal (belum ada hasil, semua "-")
function renderClassSummary(counts) {
  if (!counts) segHighlightedClassIndex = null; // reset kalau panel di-clear (belum ada hasil)
  const total = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : 0;
  classSummaryBody.innerHTML = segClassLabels
    .map((c) => {
      const count = counts ? counts[c.label] ?? 0 : null;
      const pct = counts && total > 0 ? (count / total) * 100 : 0;
      const pctText = counts ? pct.toFixed(1) + "%" : "";
      // Baris cuma bisa diklik kalau sudah ada hasil (counts != null) -- klik
      // toggle highlight kelas itu di overlay gambar (lihat toggleClassHighlight).
      const clickable = counts ? " seg-class-clickable" : "";
      const active = counts && segHighlightedClassIndex === c.index ? " seg-class-row-active" : "";
      return `
        <div class="summary-row seg-class-summary-row${clickable}${active}" data-class-index="${c.index}">
          <span><span class="seg-color-dot" style="background:${c.color}"></span>${c.label}</span>
          <span class="seg-class-summary-stats">
            <span>${count === null ? "&ndash;" : count}</span>
            ${counts ? `<span class="seg-class-pct">(${pctText})</span>` : ""}
          </span>
        </div>
      `;
    })
    .join("");

  if (counts) {
    classSummaryBody.querySelectorAll(".seg-class-clickable").forEach((el) => {
      el.addEventListener("click", () => toggleClassHighlight(parseInt(el.dataset.classIndex, 10)));
    });
  }
  renderClassChart(counts);
}

// Grafik batang horizontal jumlah sel per kelas. Panel kiri sempit (~260 px),
// jadi label kelas di kiri dan angka di kanan dalam teks HTML biasa, bukan SVG
// lebar yang diperkecil. Urutan = urutan kelas (sama dengan tabel dan tombol
// 0-9); warna batang = warna kelas (data, sama dengan overlay sel).
function renderClassChart(counts) {
  if (!counts) {
    classChartBody.innerHTML = '<span class="placeholder-text">Belum ada hasil untuk ditampilkan sebagai grafik.</span>';
    return;
  }
  const total = segClassLabels.reduce((sum, c) => sum + (counts[c.label] ?? 0), 0);
  const max = Math.max(1, ...segClassLabels.map((c) => counts[c.label] ?? 0));
  classChartBody.innerHTML = segClassLabels
    .map((c) => {
      const n = counts[c.label] ?? 0;
      const pct = total ? ((n / total) * 100).toFixed(1) : "0.0";
      const dim = segHighlightedClassIndex !== null && segHighlightedClassIndex !== c.index ? " hbar-dim" : "";
      const active = segHighlightedClassIndex === c.index ? " seg-class-row-active" : "";
      return `
        <div class="hbar-row seg-class-clickable${dim}${active}" data-class-index="${c.index}" title="${c.label}: ${n} sel (${pct}%)">
          <span class="hbar-label">${c.label}</span>
          <span class="hbar-track"><span class="hbar-fill" style="width:${(n / max) * 100}%;background:${c.color}"></span></span>
          <span class="hbar-value">${n}</span>
        </div>`;
    })
    .join("");
  classChartBody.querySelectorAll(".seg-class-clickable").forEach((el) => {
    el.addEventListener("click", () => toggleClassHighlight(parseInt(el.dataset.classIndex, 10)));
  });
}

// Klik baris/bar kelas di ringkasan -> highlight (dim yang lain) sel kelas
// itu di overlay Hasil Segmentasi. Klik lagi kelas yang sama -> matikan lagi.
function toggleClassHighlight(classIndex) {
  segHighlightedClassIndex = segHighlightedClassIndex === classIndex ? null : classIndex;
  updateClassSummaryFromDetections(); // render ulang tabel + grafik dgn state highlight terbaru
  applySegClassHighlightToOverlay();
}

function applySegClassHighlightToOverlay() {
  const svg = segResultBody.querySelector("svg");
  if (!svg) return;
  svg.querySelectorAll("polygon[data-cell-id]").forEach((p) => {
    const det = segDetections.find((d) => d.id === parseInt(p.dataset.cellId, 10));
    const idx = det ? currentClassIndex(det) : null;
    p.classList.toggle("seg-polygon-dimmed", segHighlightedClassIndex !== null && idx !== segHighlightedClassIndex);
  });
  svg.querySelectorAll("text.seg-cell-number-label").forEach((t) => {
    const det = segDetections.find((d) => d.id === parseInt(t.dataset.cellId, 10));
    const idx = det ? currentClassIndex(det) : null;
    t.classList.toggle("seg-label-dimmed", segHighlightedClassIndex !== null && idx !== segHighlightedClassIndex);
  });
}

function updateClassSummaryFromDetections() {
  const counts = {};
  segClassLabels.forEach((c) => (counts[c.label] = 0));
  segDetections.forEach((d) => {
    const label = d.correctedClassLabel || d.classLabel;
    if (label in counts) counts[label] += 1;
  });
  renderClassSummary(counts);
}

// Tab kecil khusus area gambar (Gambar Sumber <-> Hasil Segmentasi) --
// cuma satu yang ditampilkan dalam satu waktu, jadi nggak perlu dua panel
// besar berdampingan, dan sisa ruang bisa dipakai buat Daftar Sel Terdeteksi.
function switchSegImageTab(tab) {
  const isSource = tab === "source";
  segTabSource.classList.toggle("seg-image-tab-active", isSource);
  segTabResult.classList.toggle("seg-image-tab-active", !isSource);
  segSourceBody.classList.toggle("view-hidden", !isSource);
  segResultBody.classList.toggle("view-hidden", isSource);
}

// Tab kecil di panel Ringkasan klasifikasi (Tabel <-> Grafik) -- tabel tetap
// jadi tampilan utama/default (persis kayak sebelumnya), grafik batang cuma
// visualisasi tambahan yang lebih gampang dibaca sekilas.
function switchSegClassTab(tab) {
  const isTable = tab === "table";
  segClassTabTable.classList.toggle("seg-image-tab-active", isTable);
  segClassTabChart.classList.toggle("seg-image-tab-active", !isTable);
  classSummaryBody.classList.toggle("view-hidden", !isTable);
  classChartBody.classList.toggle("view-hidden", isTable);
}

// Daftar sel dan hasil folder kini tampil bersamaan (panel kanan dan kiri),
// jadi yang tersisa hanya menampilkan bar koreksi massal bila ada sel.
function switchSegListTab() {
  segBulkActionsBar.classList.toggle("view-hidden", segDetections.length === 0);
}

// -----------------------------------------------------------------------
// Zoom & pan gambar
// -----------------------------------------------------------------------
function applySegZoomTransform() {
  const transform = `translate(${segPanX}px, ${segPanY}px) scale(${segZoom})`;
  const srcImg = segSourceBody.querySelector("img");
  if (srcImg) srcImg.style.transform = transform;
  const wrap = segResultBody.querySelector(".seg-overlay-wrap");
  if (wrap) wrap.style.transform = transform;
  const cursor = segZoom > 1 ? "grab" : "default";
  segSourceBody.style.cursor = cursor;
  segResultBody.style.cursor = segAddMode ? "crosshair" : cursor;
  // Mode tambah sel: polygon sel yang sudah ada juga harus tetap kelihatan
  // "crosshair" (bukan "pointer") biar nggak membingungkan -- klik tetap
  // nambah sel baru di posisi manapun, bukan pilih sel yang sudah ada.
  if (wrap) wrap.classList.toggle("seg-add-mode-active", segAddMode);
  segZoomLabel.textContent = Math.round(segZoom * 100) + "%";
}

function resetSegZoom() {
  segZoom = 1;
  segPanX = 0;
  segPanY = 0;
  applySegZoomTransform();
}

function setSegZoom(newZoom) {
  segZoom = Math.min(4, Math.max(1, newZoom));
  if (segZoom === 1) {
    segPanX = 0;
    segPanY = 0;
  }
  applySegZoomTransform();
}

function handleSegWheelZoom(e) {
  e.preventDefault();
  setSegZoom(segZoom + (e.deltaY < 0 ? 0.15 : -0.15));
}

// Satu set handler mousedown/move/up dipakai bareng buat panel Gambar
// Sumber & Hasil Segmentasi -- kalau nggak zoom, mousedown+mouseup tanpa
// gerak berarti "klik" (dipakai buat nambah sel manual di segResultBody,
// lihat addManualCellAtEvent). Kalau lagi zoom (segZoom>1) & mouse gerak,
// itu dianggap pan/geser, bukan klik.
function segMouseDown(e) {
  if (e.button !== 0) return;
  segPanActiveEl = e.currentTarget;
  segMouseMoved = false;
  segMouseDownX = e.clientX;
  segMouseDownY = e.clientY;
  segDragStartX = e.clientX - segPanX;
  segDragStartY = e.clientY - segPanY;
}

function segMouseMove(e) {
  if (!segPanActiveEl) return;
  const dx = e.clientX - segMouseDownX;
  const dy = e.clientY - segMouseDownY;
  if (Math.abs(dx) > 4 || Math.abs(dy) > 4) segMouseMoved = true;
  if (segMouseMoved && segZoom > 1) {
    segPanX = e.clientX - segDragStartX;
    segPanY = e.clientY - segDragStartY;
    applySegZoomTransform();
  }
}

function segMouseUp(e) {
  if (!segPanActiveEl) return;
  const wasResultClick = !segMouseMoved && segPanActiveEl === segResultBody;
  const clickedInAddMode = wasResultClick && segAddMode;
  const clickedForSelect = wasResultClick && !segAddMode;
  segPanActiveEl = null;
  if (clickedInAddMode) addManualCellAtEvent(e);
  else if (clickedForSelect) trySelectCellAtEvent(e);
}

// Klik langsung di sel (polygon) pada gambar Hasil Segmentasi -- highlight
// baris yang sesuai di panel Sel Terdeteksi (scroll ke situ + tandai aktif)
// supaya user bisa langsung ganti kelasnya lewat dropdown di baris itu atau
// shortcut angka 0-9, tanpa perlu cari baris satu-satu.
function trySelectCellAtEvent(e) {
  const el = document.elementFromPoint(e.clientX, e.clientY);
  const polygon = el && el.closest ? el.closest("polygon[data-cell-id]") : null;
  if (!polygon) return;
  const cellId = parseInt(polygon.dataset.cellId, 10);
  if (isNaN(cellId)) return;
  switchSegListTab("detections"); // pastikan panel Sel Terdeteksi kelihatan (bukan Hasil Folder)
  setActiveCell(cellId);
}

// -----------------------------------------------------------------------
// Tambah/hapus deteksi sel secara manual (koreksi hasil model, bukan cuma
// koreksi kelasnya)
// -----------------------------------------------------------------------
function toggleSegAddMode() {
  segAddMode = !segAddMode;
  btnSegAddCell.classList.toggle("btn-toggle-active", segAddMode);
  applySegZoomTransform(); // ikut update cursor jadi crosshair/default
  if (segAddMode) {
    switchSegImageTab("result");
    showToast('Mode tambah sel aktif -- klik posisi sel di gambar. Tekan "Tambah sel" lagi atau Esc untuk berhenti.');
  }
}

function addManualCellAtEvent(e) {
  const svg = segResultBody.querySelector("svg");
  if (!svg || !segImgW || !segImgH) return;
  const pt = svg.createSVGPoint();
  pt.x = e.clientX;
  pt.y = e.clientY;
  const svgPt = pt.matrixTransform(svg.getScreenCTM().inverse());
  const cx = Math.round(svgPt.x);
  const cy = Math.round(svgPt.y);
  if (cx < 0 || cy < 0 || cx > segImgW || cy > segImgH) return; // klik di luar area gambar

  const r = Math.max(6, Math.round(Math.min(segImgW, segImgH) * 0.03));
  const nPoints = 16;
  const mask = [];
  for (let p = 0; p < nPoints; p++) {
    const angle = (2 * Math.PI * p) / nPoints;
    mask.push([Math.round(cx + r * Math.cos(angle)), Math.round(cy + r * Math.sin(angle))]);
  }
  const nextId = segDetections.reduce((max, d) => Math.max(max, d.id), -1) + 1;
  segDetections.push({
    id: nextId,
    classIndex: 10, // default "Uncategorised" -- belum ada prediksi model, murni manual
    classLabel: "Uncategorised",
    confidence: 1,
    bbox: [cx - r, cy - r, 2 * r, 2 * r],
    mask,
    manual: true,
    correctedClassIndex: null,
    correctedClassLabel: null,
    doctorVerdict: null,
  });
  renderSegmentationOverlay();
  renderDetectionsList();
  updateClassSummaryFromDetections();
  btnSaveSegmentation.disabled = false;
  setActiveCell(nextId);
  showToast("Sel manual ditambahkan -- atur kelasnya di daftar sel (atau tekan tombol angka).");
}

// Perbesar/perkecil sel yang lagi aktif/dipilih -- scale semua titik mask-nya
// dari centroid (polygonCentroid), jadi bentuk relatifnya tetap sama, cuma
// ukurannya yang berubah. Berlaku buat sel manapun (hasil model maupun
// tambahan manual), bukan cuma yang manual.
function resizeActiveCell(factor) {
  if (segActiveCellId === null) return;
  const det = segDetections.find((d) => d.id === segActiveCellId);
  if (!det) return;

  const [cx, cy] = polygonCentroid(det.mask);
  const avgRadius =
    det.mask.reduce((sum, [x, y]) => sum + Math.hypot(x - cx, y - cy), 0) / det.mask.length;
  const maxRadius = Math.min(segImgW, segImgH) * 0.5;
  const newRadius = avgRadius * factor;
  if (newRadius < MIN_CELL_RADIUS || newRadius > maxRadius) return; // di luar batas, batalkan

  const newMask = det.mask.map(([x, y]) => [
    Math.round(cx + (x - cx) * factor),
    Math.round(cy + (y - cy) * factor),
  ]);
  const xs = newMask.map((p) => p[0]);
  const ys = newMask.map((p) => p[1]);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  det.mask = newMask;
  det.bbox = [minX, minY, Math.max(...xs) - minX, Math.max(...ys) - minY];

  renderSegmentationOverlay();
  renderDetectionsList();
}

function deleteDetection(cellId) {
  segDetections = segDetections.filter((d) => d.id !== cellId);
  if (segActiveCellId === cellId) segActiveCellId = null;
  segSelectedCellIds.delete(cellId);
  renderSegmentationOverlay();
  renderDetectionsList();
  updateClassSummaryFromDetections();
  btnSaveSegmentation.disabled = segDetections.length === 0;
  updateCellSizeButtonsState();
}

// Sinkronkan highlight baris di Daftar Sel <-> polygon di overlay gambar,
// dipakai baik dari klik mouse maupun navigasi panah keyboard.
function setActiveCell(cellId) {
  segActiveCellId = cellId;
  segDetectionsBody.querySelectorAll(".seg-detection-row").forEach((r) => {
    r.classList.toggle("seg-row-active", parseInt(r.dataset.cellId, 10) === cellId);
  });
  const svg = segResultBody.querySelector("svg");
  if (svg) {
    svg.querySelectorAll("polygon").forEach((p) => {
      p.classList.toggle("seg-polygon-active", parseInt(p.dataset.cellId, 10) === cellId);
    });
  }
  const activeRow = segDetectionsBody.querySelector(`.seg-detection-row[data-cell-id="${cellId}"]`);
  // Gulir daftar sel saja (bukan panel kanan), supaya inspektur sel tetap di
  // tempatnya saat pilihan pindah otomatis setelah verdict.
  if (activeRow) {
    const r = activeRow.getBoundingClientRect();
    const box = segDetectionsBody.getBoundingClientRect();
    if (r.top < box.top || r.bottom > box.bottom) {
      segDetectionsBody.scrollTop += r.top - box.top - (box.height - r.height) / 2;
    }
  }
  updateCellSizeButtonsState();
  renderInspector();
}

// Tombol resize (dan shortcut +/-) cuma masuk akal kalau ada sel yang lagi
// dipilih -- dipanggil tiap kali segActiveCellId berubah (pilih/hapus/reset).
function updateCellSizeButtonsState() {
  const disabled = segActiveCellId === null;
  btnSegCellShrink.disabled = disabled;
  btnSegCellGrow.disabled = disabled;
}

function resetSegmentationResults() {
  segDetections = [];
  updateSegTotalCellCount();
  segHighlightedClassIndex = null;
  segActiveCellId = null;
  segAddMode = false;
  segSelectedCellIds = new Set();
  segSelectAllCells.checked = false;
  btnSegAddCell.classList.remove("btn-toggle-active");
  btnSegAddCell.disabled = true;
  updateCellSizeButtonsState();
  resetSegZoom();
  segResultBody.innerHTML =
    '<span class="placeholder-text">Belum ada hasil<br />Klik "Jalankan segmentasi" (hasilnya masih data dummy/placeholder)</span>';
  segDetectionsBody.innerHTML = '<div class="summary-row">Belum ada hasil.</div>';
  segBulkActionsBar.classList.add("view-hidden");
  renderInspector();
  renderClassSummary(null);
  btnSaveSegmentation.disabled = true;
  switchSegImageTab("source");
}

// File hasil Capture disimpan dengan pola "inisial-pasien_timestamp_iterasi.ext"
// (lihat doSave() -- backend format-nya "{slug}_{timestamp}_{iterasi}").
// Kalau nama file yang dipilih persis cocok pola ini, tebak inisial
// pasiennya dari situ -- biar field ID Pasien nggak kosong/ke-lewat pas
// user pilih gambar langsung dari dialog file (bukan lewat "Kirim ke
// Segmentasi" dari tab Capture), yang tadinya bikin field itu kosong dan
// akhirnya tersimpan sebagai "?" di segmentation_log.csv.
function guessPatientIdFromFilename(pathOrFilename) {
  const base = (pathOrFilename || "").split(/[\\/]/).pop() || "";
  const withoutExt = base.replace(/\.[^.]+$/, "");
  const m = withoutExt.match(/^([a-z0-9-]+)_(\d{8}-\d{6})_(\d+)$/i);
  return m ? m[1] : "";
}

async function doSelectSegmentationImage() {
  btnSegSelectImage.disabled = true;
  btnSegSelectImage.textContent = "Memilih...";
  const res = await fetch("/api/segmentation/select-image", { method: "POST" });
  btnSegSelectImage.disabled = false;
  btnSegSelectImage.textContent = "Pilih gambar";
  const data = await res.json();
  if (!data.ok) {
    if (data.message) showError(data.message);
    return;
  }
  segSelectedPath = data.path;
  segActiveFolder = segFolderOf(data.path);
  segCurrentImageDataUrl = `data:image/png;base64,${data.image}`;
  segImagePathEl.textContent = "Gambar: " + data.path;
  segSourceBody.innerHTML = `<img src="${segCurrentImageDataUrl}" alt="${data.filename}" />`;
  segPatientNameInput.value = guessPatientIdFromFilename(data.path || data.filename);
  btnRunSegmentation.disabled = false;
  resetSegmentationResults();
}

// Logic bersama buat menerapkan hasil segmentasi yang dimuat balik ke UI --
// dipakai baik lewat dialog file (doLoadSegmentationResult) maupun klik
// langsung di daftar "Hasil di Folder Ini" (doLoadSegmentationResultByPath),
// jadi kontraknya konsisten dari dua jalur itu.
function applyLoadedSegmentationResult(data) {
  segSelectedPath = data.path;
  if (data.path) segActiveFolder = segFolderOf(data.path);
  // Hasil lama yang disimpan sebelum inisial pasien wajib/otomatis terisi
  // bisa aja patientId-nya kosong -- coba tebak dari nama file gambar
  // sumbernya (lihat guessPatientIdFromFilename) daripada dibiarkan kosong.
  segPatientNameInput.value =
    data.patientId && data.patientId !== "?"
      ? data.patientId
      : guessPatientIdFromFilename(data.path) || guessPatientIdFromFilename(data.detailFile);
  segImagePathEl.textContent = data.path
    ? "Gambar: " + data.path + (data.detailFile ? ` (dimuat dari ${data.detailFile})` : "")
    : `Dimuat dari ${data.detailFile} (path gambar sumber tidak tercatat)`;

  segDetections = (data.detections || []).map((d) => ({
    ...d,
    correctedClassIndex: d.correctedClassIndex ?? null,
    correctedClassLabel: d.correctedClassLabel ?? null,
    doctorVerdict: d.doctorVerdict ?? null, // kompatibel dgn file lama sblm fitur ini ada
  }));
  segCleanJson = JSON.stringify(segDetections);
  if (data.labelMode) segLabelMode = data.labelMode;
  segActiveCellId = null;
  updateCellSizeButtonsState();
  segAddMode = false;
  segHighlightedClassIndex = null;
  segSelectedCellIds = new Set();
  segSelectAllCells.checked = false;
  btnSegAddCell.classList.remove("btn-toggle-active");
  resetSegZoom();

  if (data.image) {
    segCurrentImageDataUrl = `data:image/png;base64,${data.image}`;
    segImgW = data.width;
    segImgH = data.height;
    segSourceBody.innerHTML = `<img src="${segCurrentImageDataUrl}" alt="sumber" />`;
    renderSegmentationOverlay();
    btnRunSegmentation.disabled = false;
    btnSegAddCell.disabled = false;
    switchSegImageTab("result");
  } else {
    segCurrentImageDataUrl = null;
    const missingMsg =
      '<span class="placeholder-text">Gambar sumber asli tidak ditemukan di lokasi semula<br />Daftar sel tetap bisa dilihat/dikoreksi di sebelah kanan</span>';
    segSourceBody.innerHTML = missingMsg;
    segResultBody.innerHTML = missingMsg;
    btnRunSegmentation.disabled = true;
    btnSegAddCell.disabled = true; // butuh gambar buat tahu posisi klik -> koordinat piksel
    switchSegImageTab("source");
    if (data.message) showToast(data.message);
  }

  renderDetectionsList();
  updateClassSummaryFromDetections();
  btnSaveSegmentation.disabled = segDetections.length === 0;
}

// Muat balik hasil segmentasi yang sudah pernah disimpan lewat dialog pilih
// file JSON manual -- biar bisa dilihat & dikoreksi lagi tanpa perlu
// jalankan ulang dari nol.
async function doLoadSegmentationResult() {
  btnLoadSegmentation.disabled = true;
  btnLoadSegmentation.textContent = "Memuat...";
  const res = await fetch("/api/segmentation/load", { method: "POST" });
  const data = await res.json();
  btnLoadSegmentation.disabled = false;
  btnLoadSegmentation.textContent = "Muat hasil tersimpan";

  if (!data.ok) {
    if (data.message) showError(data.message);
    return;
  }
  applyLoadedSegmentationResult(data);
}

// Sama seperti di atas, tapi path file JSON-nya sudah diketahui (diklik dari
// daftar "Hasil di Folder Ini") -- TANPA buka dialog file lagi. Ini yang
// bikin review banyak hasil sekaligus (mis. satu pasien ~20 capture, hasil
// dari Proses Batch) jadi cuma klik-klik di dalam aplikasi, bukan
// buka-tutup dialog OS satu-satu per gambar.
async function doLoadSegmentationResultByPath(detailPath) {
  const res = await fetch("/api/segmentation/load-path", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: detailPath }),
  });
  const data = await res.json();
  if (!data.ok) {
    if (!data.offline) showError(data.message || "Gagal memuat hasil.");
    return;
  }
  applyLoadedSegmentationResult(data);
}

// Dipanggil dari tombol "Kirim ke Segmentasi" di tab Capture -- pakai
// gambar & path yang baru saja disimpan (lastSavedFullPath/lastCapturedImage
// dari doSave()), jadi user nggak perlu buka file dialog manual lagi.
function sendCaptureToSegmentation() {
  if (!lastSavedFullPath) return;
  segSelectedPath = lastSavedFullPath;
  segActiveFolder = segFolderOf(lastSavedFullPath);
  segCurrentImageDataUrl = lastCapturedImage ? `data:image/png;base64,${lastCapturedImage}` : null;
  segImagePathEl.textContent = "Gambar: " + segSelectedPath;
  segPatientNameInput.value = patientNameInput.value.trim();
  segSourceBody.innerHTML = segCurrentImageDataUrl
    ? `<img src="${segCurrentImageDataUrl}" alt="sumber" />`
    : '<span class="placeholder-text">Gambar tersimpan. Klik "Jalankan segmentasi".</span>';
  btnRunSegmentation.disabled = false;
  resetSegmentationResults();
  switchTab("segmentation");
  showToast("Gambar dikirim ke layar Analisis sel.");
}

function currentClassIndex(d) {
  return d.correctedClassIndex !== null && d.correctedClassIndex !== undefined
    ? d.correctedClassIndex
    : d.classIndex;
}

// Centroid kasar (rata-rata titik mask) -- cukup akurat buat penempatan
// label nomor di tengah sel bulat/cembung seperti RBC, nggak perlu hitung
// centroid area yang lebih presisi.
function polygonCentroid(mask) {
  const n = mask.length;
  let sumX = 0;
  let sumY = 0;
  mask.forEach(([x, y]) => {
    sumX += x;
    sumY += y;
  });
  return [sumX / n, sumY / n];
}

// Bagian hasil model yang ditimpa dokter: "kelas" dan, untuk model atribut,
// "ukuran"/"warna"/"bentuk". Sel tambahan dokter (manual) bukan koreksi.
function correctedParts(d) {
  if (d.manual) return [];
  const parts = [];
  if (d.correctedClassIndex !== null && d.correctedClassIndex !== undefined && d.correctedClassIndex !== d.classIndex) {
    parts.push("kelas");
  }
  const m = d.attributes;
  const c = d.correctedAttributes;
  if (m && c) {
    if ((m.ukuran || null) !== (c.ukuran || null)) parts.push("ukuran");
    if ((m.warna || null) !== (c.warna || null)) parts.push("warna");
    if ([...m.bentuk].sort().join() !== [...c.bentuk].sort().join()) parts.push("bentuk");
  }
  return parts;
}

function renderSegmentationOverlay() {
  const colorFor = (idx) => (segClassLabels[idx] ? segClassLabels[idx].color : "#64748b");
  // Ukuran font label nomor diskalakan relatif ke dimensi gambar (bukan
  // ukuran layar) karena SVG viewBox pakai satuan pixel gambar asli --
  // biar tetap terbaca proporsional baik di gambar kecil maupun besar.
  const numberFontSize = Math.max(14, Math.round(Math.min(segImgW, segImgH) * 0.018));
  let polygons = "";
  let labels = "";
  segDetections.forEach((d, i) => {
    const idx = currentClassIndex(d);
    const pts = d.mask.map((p) => p.join(",")).join(" ");
    // Confidence rendah -> garis putus-putus, biar langsung kelihatan mana
    // yang perlu diprioritaskan dicek manual.
    const dashed = !d.manual && d.confidence < segLowConfidenceThreshold ? ' stroke-dasharray="4,3"' : "";
    const activeClass = d.id === segActiveCellId ? ' class="seg-polygon-active"' : "";
    polygons += `<polygon data-cell-id="${d.id}" points="${pts}" fill="${colorFor(idx)}33" stroke="${colorFor(idx)}" stroke-width="2"${dashed}${activeClass} />`;
    // Nomor label ini match sama "Sel #${i+1}" di daftar (renderDetectionsList)
    // supaya user gampang korelasikan mask di gambar dengan baris di daftar --
    // bisa disembunyikan lewat checkbox "Tampilkan Nomor Sel" (segShowCellNumbers)
    // kalau lagi mengganggu pandangan pas menilai gambar polos.
    const [bx, by, bw] = d.bbox;
    const mr = numberFontSize * 0.42;
    if (d.manual) {
      labels += `<rect class="seg-mark" data-cell-id="${d.id}" x="${bx + bw - mr}" y="${by - mr}" width="${mr * 1.6}" height="${mr * 1.6}" transform="rotate(45 ${bx + bw - mr * 0.2} ${by - mr * 0.2})" />`;
    } else if (correctedParts(d).length) {
      labels += `<circle class="seg-mark" data-cell-id="${d.id}" cx="${bx + bw}" cy="${by}" r="${mr}" />`;
    }
    if (segShowCellNumbers) {
      const [cx, cy] = polygonCentroid(d.mask);
      labels += `<text class="seg-cell-number-label" data-cell-id="${d.id}" x="${cx}" y="${cy}" text-anchor="middle" dominant-baseline="middle" font-size="${numberFontSize}">${i + 1}</text>`;
    }
  });
  segResultBody.innerHTML = `
    <div class="seg-overlay-wrap">
      <img src="${segCurrentImageDataUrl}" alt="hasil segmentasi" />
      <svg viewBox="0 0 ${segImgW} ${segImgH}" preserveAspectRatio="xMidYMid meet">${polygons}${labels}</svg>
    </div>
    <div class="seg-legend" aria-hidden="true"><span class="mark-dot"></span> dikoreksi dokter <span class="mark-diamond"></span> ditambah dokter <span class="mark-dash"></span> keyakinan rendah</div>
  `;
  applySegZoomTransform();
  applySegClassHighlightToOverlay();
}

// Dipanggil tiap kali segDetections berubah (termasuk tiap klik tombol
// verdict dokter, lewat renderDetectionsList) -- biar jumlah sel + statistik
// review dokter di samping tombol "Hasil Segmentasi" selalu konsisten sama
// daftar sel & overlay, update live tanpa perlu Simpan/reload dulu.
function updateSegTotalCellCount() {
  if (segDetections.length === 0) {
    segTotalCellCount.textContent = "";
    return;
  }
  const correct = segDetections.filter((d) => d.doctorVerdict === "correct").length;
  const incorrect = segDetections.filter((d) => d.doctorVerdict === "incorrect").length;
  const reviewed = correct + incorrect;
  const verdictText = reviewed > 0 ? `, direview ${reviewed}/${segDetections.length} (✓${correct} ✗${incorrect})` : "";
  segTotalCellCount.textContent = `Jumlah sel terdeteksi: ${segDetections.length} sel${verdictText}`;
}

// -----------------------------------------------------------------------
// UC-10: draf koreksi yang belum disimpan, di browser. segCleanJson = isi
// terakhir yang sama dengan file tersimpan (null = hasil belum pernah disimpan).
// -----------------------------------------------------------------------
let segCleanJson = null;

function saveSegDraft() {
  if (!segSelectedPath || segDetections.length === 0 || JSON.stringify(segDetections) === segCleanJson) {
    localStorage.removeItem("adt-seg-draft");
    return;
  }
  localStorage.setItem(
    "adt-seg-draft",
    JSON.stringify({
      path: segSelectedPath,
      patientId: segPatientNameInput.value.trim(),
      detections: segDetections,
      time: Date.now(),
    })
  );
}

async function offerSegDraftRecovery() {
  let d;
  try {
    d = JSON.parse(localStorage.getItem("adt-seg-draft") || "null");
  } catch (e) {
    d = null;
  }
  if (!d || !d.path || !(d.detections || []).length) return;
  const name = d.path.split(/[\\/]/).pop();
  const when = new Date(d.time).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" });
  const go = await showChoiceModal(
    `Ada koreksi segmentasi yang belum disimpan untuk ${name} (${d.detections.length} sel, ${when}). Lanjutkan?`,
    [
      { label: "Buang", value: false },
      { label: "Lanjutkan", value: true, primary: true },
    ]
  );
  if (!go) {
    localStorage.removeItem("adt-seg-draft");
    return;
  }
  const res = await fetch("/api/segmentation/open-path", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: d.path }),
  });
  const data = await res.json();
  if (!data.ok) {
    if (!data.offline) showError(data.message || "Gambar sumber draf tidak bisa dibuka.");
    return;
  }
  resetSegmentationResults();
  segSelectedPath = data.path;
  segActiveFolder = segFolderOf(data.path);
  segCurrentImageDataUrl = `data:image/png;base64,${data.image}`;
  segImgW = data.width;
  segImgH = data.height;
  segImagePathEl.textContent = "Gambar: " + data.path + " (draf dipulihkan)";
  segSourceBody.innerHTML = `<img src="${segCurrentImageDataUrl}" alt="${data.filename}" />`;
  segPatientNameInput.value = d.patientId || "";
  segDetections = d.detections;
  segCleanJson = null;
  btnRunSegmentation.disabled = false;
  btnSegAddCell.disabled = false;
  btnSaveSegmentation.disabled = false;
  renderSegmentationOverlay();
  renderDetectionsList();
  updateClassSummaryFromDetections();
  switchSegImageTab("result");
  switchTab("segmentation");
}

function renderDetectionsList() {
  updateSegTotalCellCount();
  saveSegDraft();
  switchSegListTab();
  renderInspector();
  if (segDetections.length === 0) {
    segDetectionsBody.innerHTML = '<div class="summary-row">Tidak ada sel terdeteksi.</div>';
    return;
  }
  segDetectionsBody.innerHTML = segDetections
    .map((d, i) => {
      const selectedIdx = currentClassIndex(d);
      const options = segClassLabels
        .map((c) => `<option value="${c.index}" ${c.index === selectedIdx ? "selected" : ""}>${c.label}</option>`)
        .join("");
      const corrected = correctedParts(d).length
          ? ` <span class="seg-corrected-tag">dikoreksi: ${correctedParts(d).join(", ")}</span>`
          : "";
      const manualTag = d.manual ? ' <span class="seg-manual-tag">manual</span>' : "";
      const lowConf =
        !d.manual && d.confidence < segLowConfidenceThreshold
          ? ' <span class="seg-low-conf-tag">confidence rendah</span>'
          : "";
      const rowClass =
        "summary-row seg-detection-row" +
        (!d.manual && d.confidence < segLowConfidenceThreshold ? " seg-row-low-confidence" : "") +
        (d.id === segActiveCellId ? " seg-row-active" : "");
      const checked = segSelectedCellIds.has(d.id) ? " checked" : "";
      // Penilaian dokter: apakah klasifikasi sel ini benar/salah menurut
      // reviewer -- independen dari correctedClassIndex (dokter bisa saja
      // menandai "salah" tanpa langsung mengganti kelasnya, atau sebaliknya).
      const verdictCorrectActive = d.doctorVerdict === "correct" ? " active" : "";
      const verdictIncorrectActive = d.doctorVerdict === "incorrect" ? " active" : "";
      return `
        <div class="${rowClass}" data-cell-id="${d.id}">
          <input type="checkbox" class="seg-cell-checkbox" data-cell-id="${d.id}"${checked} />
          <span>Sel #${i + 1} (conf. ${(d.confidence * 100).toFixed(0)}%)${corrected}${manualTag}${lowConf}</span>
          <div class="seg-row-controls">
            <select class="seg-class-select" data-cell-id="${d.id}">${options}</select>
            <button type="button" class="seg-doctor-btn seg-doctor-btn-correct${verdictCorrectActive}" data-cell-id="${d.id}" data-verdict="correct" title="Tandai klasifikasi ini BENAR (penilaian dokter)">&check;</button>
            <button type="button" class="seg-doctor-btn seg-doctor-btn-incorrect${verdictIncorrectActive}" data-cell-id="${d.id}" data-verdict="incorrect" title="Tandai klasifikasi ini SALAH (penilaian dokter)">&cross;</button>
            <button type="button" class="seg-delete-btn" data-cell-id="${d.id}" title="Hapus deteksi ini">&times;</button>
          </div>
        </div>
      `;
    })
    .join("");

  segDetectionsBody.querySelectorAll(".seg-class-select").forEach((sel) => {
    sel.addEventListener("click", (e) => e.stopPropagation());
    sel.addEventListener("change", (e) => {
      const cellId = parseInt(e.target.dataset.cellId, 10);
      const newIndex = parseInt(e.target.value, 10);
      const det = segDetections.find((d) => d.id === cellId);
      if (!det) return;
      det.correctedClassIndex = newIndex;
      det.correctedClassLabel = segClassLabels[newIndex].label;
      renderDetectionsList();
      renderSegmentationOverlay();
      updateClassSummaryFromDetections();
    });
  });

  segDetectionsBody.querySelectorAll(".seg-doctor-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const cellId = parseInt(btn.dataset.cellId, 10);
      const det = segDetections.find((d) => d.id === cellId);
      if (!det) return;
      const verdict = btn.dataset.verdict;
      // Klik tombol yang sama dua kali -> batalkan (balik ke "belum direview").
      det.doctorVerdict = det.doctorVerdict === verdict ? null : verdict;
      renderDetectionsList();
    });
  });

  segDetectionsBody.querySelectorAll(".seg-delete-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteDetection(parseInt(btn.dataset.cellId, 10));
    });
  });

  segDetectionsBody.querySelectorAll(".seg-cell-checkbox").forEach((cb) => {
    cb.addEventListener("click", (e) => e.stopPropagation());
    cb.addEventListener("change", (e) => {
      const cellId = parseInt(e.target.dataset.cellId, 10);
      if (e.target.checked) segSelectedCellIds.add(cellId);
      else segSelectedCellIds.delete(cellId);
      segSelectAllCells.checked = segSelectedCellIds.size === segDetections.length;
    });
  });

  segDetectionsBody.querySelectorAll(".seg-detection-row").forEach((row) => {
    row.addEventListener("click", () => setActiveCell(parseInt(row.dataset.cellId, 10)));
  });
}

async function doRunSegmentation() {
  if (!segSelectedPath) return;

  // Peringatan kalau gambar ini sudah pernah diproses sebelumnya (individual
  // atau lewat batch) -- biar user sadar hasil lama bakal "tergantikan" di
  // tampilan (lihat dedup di list-results/patient-summary), meski riwayatnya
  // tetap tersimpan penuh di segmentation_log.csv.
  try {
    const checkRes = await fetch(
      "/api/segmentation/check-existing?path=" + encodeURIComponent(segSelectedPath)
    );
    const checkData = await checkRes.json();
    if (checkData.exists) {
      const lanjut = await showConfirmModal(
        `Gambar ini sudah pernah diproses sebelumnya (${checkData.totalCells} sel, ` +
        `${checkData.timestamp}).\n\nJalankan ulang? Hasil baru akan menggantikan ` +
        `tampilan hasil lama (riwayat lama tetap tersimpan di segmentation_log.csv).`
      );
      if (!lanjut) return;
    }
  } catch (e) {
    // Kalau pengecekan gagal (mis. jaringan), lanjut proses seperti biasa --
    // ini cuma peringatan tambahan, bukan syarat wajib.
  }

  btnRunSegmentation.disabled = true;
  btnRunSegmentation.textContent = "Memproses...";
  segResultBody.innerHTML =
    '<span class="placeholder-text">Memproses segmentasi (dummy)...<br />Model beneran belum terpasang</span>';

  const res = await fetch("/api/segmentation/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: segSelectedPath }),
  });
  const data = await res.json();
  btnRunSegmentation.disabled = false;
  btnRunSegmentation.textContent = "Jalankan segmentasi";

  if (!data.ok) {
    if (!data.offline) showError(data.message || "Gagal memproses segmentasi.");
    resetSegmentationResults();
    return;
  }

  segImgW = data.imageWidth;
  segImgH = data.imageHeight;
  segDetections = data.detections.map((d) => ({
    ...d,
    correctedClassIndex: null,
    correctedClassLabel: null,
    doctorVerdict: null,
  }));
  segActiveCellId = null;
  updateCellSizeButtonsState();
  segAddMode = false;
  segHighlightedClassIndex = null;
  segSelectedCellIds = new Set();
  segSelectAllCells.checked = false;
  btnSegAddCell.classList.remove("btn-toggle-active");
  btnSegAddCell.disabled = false;
  resetSegZoom();
  renderSegmentationOverlay();
  renderDetectionsList();
  updateClassSummaryFromDetections();
  btnSaveSegmentation.disabled = false;
  switchSegImageTab("result");
  if (data.mock) showToast(data.message);
}

async function doSaveSegmentation() {
  if (!segSelectedPath || segDetections.length === 0) return;
  await trySaveSegmentation(false);
}

// force=false: cek dulu ke server apakah hasil ini persis sama (jumlah sel
// per kelas identik) dengan hasil TERAKHIR yang sudah tersimpan buat gambar
// ini -- kalau iya, server belum nulis apa-apa & balikin needsConfirmation,
// baru di sini ditanya ke user mau tetap disimpan sebagai duplikat atau
// tidak (force=true buat beneran nulis). Ini nyegah folder numpuk banyak
// file JSON isinya sama persis tanpa disadari user.
async function trySaveSegmentation(force) {
  btnSaveSegmentation.disabled = true;
  btnSaveSegmentation.textContent = "Menyimpan...";

  const res = await fetch("/api/segmentation/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      path: segSelectedPath,
      patientId: segPatientNameInput.value.trim(),
      detections: segDetections,
      labelMode: segLabelMode,
      force,
    }),
  });
  const data = await res.json();
  btnSaveSegmentation.disabled = false;
  btnSaveSegmentation.textContent = "Simpan hasil";

  if (!data.ok) {
    if (!data.offline) showError(data.message || "Gagal menyimpan hasil.", { label: "Coba simpan lagi", run: doSaveSegmentation });
    return;
  }

  if (data.needsConfirmation) {
    const lanjut = await showConfirmModal(
      `Hasil ini sama persis (sel, kelas, dan penilaian dokter) dengan hasil tersimpan ` +
      `terakhir untuk gambar ini (${data.lastDetailFile}, ${data.lastTimestamp}).\n\n` +
      `Simpan lagi sebagai duplikat?`
    );
    if (lanjut) await trySaveSegmentation(true);
    return;
  }

  segCleanJson = JSON.stringify(segDetections);
  localStorage.removeItem("adt-seg-draft");
  const dupNote = data.isDuplicate ? " (ditandai duplikat)" : "";
  showToast(
    `Tersimpan (${data.totalCells} sel)${dupNote} -- lihat segmentation_log.csv di folder gambar sumber.`
  );
}

// -----------------------------------------------------------------------
// Ringkasan per pasien (agregasi segmentation_log.csv di folder gambar
// aktif) & proses batch satu folder sekaligus
// -----------------------------------------------------------------------
function segFolderOf(path) {
  const idx = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
  return idx >= 0 ? path.substring(0, idx) : path;
}

async function doLoadSegPatientSummary() {
  if (!segActiveFolder) {
    showToast("Pilih/muat gambar dulu (atau proses satu folder) supaya tahu folder yang mau diringkas.");
    return;
  }
  const folder = segActiveFolder;
  btnSegPatientSummary.disabled = true;
  btnSegPatientSummary.textContent = "Memuat...";
  const res = await fetch("/api/segmentation/patient-summary?folder=" + encodeURIComponent(folder));
  const data = await res.json();
  btnSegPatientSummary.disabled = false;
  btnSegPatientSummary.textContent = "Muat ringkasan per pasien";

  if (!data.ok) {
    segPatientSummaryBody.innerHTML = `<div class="summary-row">${data.message || "Gagal memuat."}</div>`;
    return;
  }
  if (data.patients.length === 0) {
    segPatientSummaryBody.innerHTML = '<div class="summary-row">Belum ada hasil tersimpan di folder ini.</div>';
    return;
  }
  segPatientSummaryBody.innerHTML = data.patients
    .map((p) => {
      const verdictText =
        p.totalReviewed > 0
          ? `, direview ${p.totalReviewed} (✓${p.totalCorrect} ✗${p.totalIncorrect})`
          : "";
      return `<div class="summary-row"><span>${p.patientId}</span><span>${p.totalImages} gambar, ${p.totalCells} sel${verdictText}</span></div>`;
    })
    .join("");
}

// Export ringkasan folder aktif ke file Excel (server yang nulis file-nya
// langsung ke folder gambar sumber, sama seperti segmentation_log.csv) --
// kalau ID pasien diisi di field atas, cuma pasien itu yang diekspor.
async function doExportSegReport() {
  if (!segActiveFolder) {
    showToast("Pilih/muat gambar dulu (atau proses satu folder) supaya tahu folder yang mau diekspor.");
    return;
  }
  btnSegExportReport.disabled = true;
  btnSegExportReport.textContent = "Mengekspor...";
  const res = await fetch("/api/segmentation/export-report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      folder: segActiveFolder,
      patientId: segPatientNameInput.value.trim(),
    }),
  });
  const data = await res.json();
  btnSegExportReport.disabled = false;
  btnSegExportReport.textContent = "Export laporan (Excel)";

  if (!data.ok) {
    if (!data.offline) showError(data.message || "Gagal mengekspor laporan.");
    return;
  }
  showToast("Laporan tersimpan: " + data.filename);
}

// Export hasil segmentasi folder aktif ke format COCO (annotations.json) --
// siap dipakai training Mask R-CNN/Detectron2, beda dari Export Laporan
// (Excel) yang buat dibaca manusia. Checkbox "Hanya yang sudah direview"
// menentukan apakah sel yang belum ditandai Benar/Salah ikut atau tidak
// (lihat penjelasan lengkap di api_segmentation_export_coco).
async function doExportSegDatasetCoco() {
  if (!segActiveFolder) {
    showToast("Pilih/muat gambar dulu (atau proses satu folder) supaya tahu folder yang mau diekspor.");
    return;
  }
  btnSegExportCoco.disabled = true;
  btnSegExportCoco.textContent = "Mengekspor...";
  const res = await fetch("/api/segmentation/export-coco", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      folder: segActiveFolder,
      patientId: segPatientNameInput.value.trim(),
      onlyReviewed: segCocoOnlyReviewedCheckbox.checked,
    }),
  });
  const data = await res.json();
  btnSegExportCoco.disabled = false;
  btnSegExportCoco.textContent = "Export dataset (COCO)";

  if (data.ok) showToast(data.message || "Dataset tersimpan.");
  else if (!data.offline) showError(data.message || "Gagal mengekspor dataset.");
}

// Render daftar hasil yang bisa diklik -- setiap baris, kalau diklik,
// langsung buka hasil itu buat direview/dikoreksi (doLoadSegmentationResultByPath),
// TANPA dialog file. Dipakai baik dipanggil manual (tombol "Muat Daftar")
// maupun otomatis begitu Proses Batch selesai.
function renderSegResultsList(results) {
  if (results.length === 0) {
    const msg = segResultsFilter.value.trim()
      ? "Tidak ada hasil yang cocok dengan filter."
      : "Belum ada hasil tersimpan di folder ini.";
    segResultsListBody.innerHTML = `<div class="summary-row">${msg}</div>`;
    return;
  }
  segResultsListBody.innerHTML = results
    .map((r) => {
      const filename = r.sourceImage ? r.sourceImage.split(/[\\/]/).pop() : r.detailFile;
      const patientTag = r.patientId && r.patientId !== "?" ? ` (${r.patientId})` : "";
      // Baris kedua nunjukin nama file JSON detail aslinya (persis kayak di
      // File Explorer/folder gambar) -- biar jelas file mana persisnya yang
      // dipakai buat gambar ini, nggak cuma nama gambar sumbernya.
      const fileSubtitle =
        r.detailFile && r.detailFile !== filename
          ? `<span class="seg-result-list-file" title="${r.detailFile}">${r.detailFile}</span>`
          : "";
      // Hasil yang jumlah sel per kelasnya PERSIS SAMA dengan hasil
      // sebelumnya (lihat check duplikat di doSaveSegmentation) ditandai di
      // sini, biar kelihatan sekilas mana yang kemungkinan nggak perlu.
      const dupTag = r.isDuplicate
        ? ` <span class="seg-duplicate-tag" title="${r.duplicateOfFile ? "Sama dengan: " + r.duplicateOfFile : ""}">duplikat</span>`
        : "";
      return `
        <div class="summary-row seg-result-list-row" data-path="${r.detailPath}">
          <div class="seg-result-list-main">
            <span class="seg-result-list-title">${filename}${patientTag}${dupTag}</span>
            ${fileSubtitle}
          </div>
          <span>${r.totalCells} sel</span>
        </div>
      `;
    })
    .join("");
  segResultsListBody.querySelectorAll(".seg-result-list-row").forEach((row) => {
    row.addEventListener("click", () => doLoadSegmentationResultByPath(row.dataset.path));
  });
}

// Filter murni di sisi client (dari segResultsListCache) -- nggak perlu
// fetch ulang server tiap ngetik, cocok berat filter nama file/ID pasien
// buat folder isi ~20 gambar seperti kasus nyata.
function applySegResultsFilter() {
  const q = segResultsFilter.value.trim().toLowerCase();
  if (!q) {
    renderSegResultsList(segResultsListCache);
    return;
  }
  const filtered = segResultsListCache.filter((r) => {
    const filename = (r.sourceImage ? r.sourceImage.split(/[\\/]/).pop() : r.detailFile) || "";
    const patientId = r.patientId || "";
    return filename.toLowerCase().includes(q) || patientId.toLowerCase().includes(q);
  });
  renderSegResultsList(filtered);
}

async function loadSegResultsListForFolder(folder) {
  const res = await fetch("/api/segmentation/list-results?folder=" + encodeURIComponent(folder));
  const data = await res.json();
  if (!data.ok) {
    segResultsListCache = [];
    segResultsListBody.innerHTML = `<div class="summary-row">${data.message || "Gagal memuat daftar."}</div>`;
    return;
  }
  segResultsListCache = data.results;
  applySegResultsFilter();
}

// Tombol "Muat Daftar" -- pakai folder dari gambar yang lagi aktif/dipilih.
// Kalau belum ada gambar dipilih sama sekali (mis. baru buka app dan mau
// langsung lihat hasil batch dari sesi sebelumnya), jalankan Proses Batch
// dulu atau pilih satu gambar dulu supaya foldernya diketahui.
async function doLoadSegResultsListButton() {
  switchSegListTab("folder");
  if (!segActiveFolder) {
    showToast("Pilih/muat gambar dulu (atau proses satu folder) supaya tahu folder yang mau dibuka.");
    return;
  }
  btnSegListResults.disabled = true;
  await loadSegResultsListForFolder(segActiveFolder);
  btnSegListResults.disabled = false;
}

async function doSegBatchRun() {
  btnSegBatchRun.disabled = true;
  btnSegBatchRun.textContent = "Memilih folder...";
  const selectRes = await fetch("/api/segmentation/batch-select", { method: "POST" });
  const selectData = await selectRes.json();
  btnSegBatchRun.disabled = false;
  btnSegBatchRun.textContent = "Proses satu folder";

  if (!selectData.ok) return;
  if (selectData.files.length === 0) {
    showToast("Tidak ada file gambar di folder itu.");
    return;
  }

  const ratingNote =
    (selectData.unworthy ? `${selectData.unworthy} citra dinilai tidak layak oleh dokter dan akan dilewati. ` : "") +
    (selectData.unrated ? `${selectData.unrated} citra belum dinilai di layar Penilaian citra (tetap diproses).` : "");
  const choice = await showChoiceModal(
    `Ditemukan ${selectData.files.length} gambar di folder ini.` + (ratingNote ? `\n\n${ratingNote}` : "") + `\n\n` +
    `Proses semua sekaligus? Hasilnya masih DUMMY/placeholder dan langsung ` +
    `tersimpan (JSON detail + segmentation_log.csv). Setelah selesai, semua ` +
    `hasilnya bisa dibuka satu-satu langsung dari daftar "Hasil di Folder ` +
    `Ini" (tanpa dialog file lagi) buat direview/dikoreksi.\n\n` +
    `Gambar yang sudah pernah diproses sebelumnya bisa dilewati (skip) supaya ` +
    `tidak menumpuk hasil baru yang random di atas hasil yang sudah dikoreksi.`,
    [
      { label: "Batal", value: null },
      { label: "Lewati yang Sudah Ada", value: "skip" },
      { label: "Proses Semua", value: "all", primary: true },
    ]
  );
  if (!choice) return;

  btnSegBatchRun.disabled = true;
  btnSegBatchRun.textContent = "Memproses...";
  switchSegListTab("folder");
  segResultsListBody.innerHTML = `<div class="summary-row">Memproses ${selectData.files.length} gambar, mohon tunggu...</div>`;

  const runRes = await fetch("/api/segmentation/batch-run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      folder: selectData.folder,
      patientId: segPatientNameInput.value.trim(),
      skipExisting: choice === "skip",
    }),
  });
  const runData = await runRes.json();
  btnSegBatchRun.disabled = false;
  btnSegBatchRun.textContent = "Proses satu folder";

  if (!runData.ok) {
    segResultsListBody.innerHTML = `<div class="summary-row">${runData.message || "Gagal memproses batch."}</div>`;
    return;
  }

  // Set folder aktif ke folder batch ini, biar tombol "Muat Daftar" &
  // Ringkasan per Pasien juga langsung nunjuk ke folder yang barusan
  // diproses (bukan cuma daftar hasil di bawah ini doang).
  segActiveFolder = selectData.folder;
  await loadSegResultsListForFolder(selectData.folder);
  const skippedText =
    (runData.totalSkipped ? `, ${runData.totalSkipped} dilewati (sudah ada)` : "") +
    (runData.totalUnworthy ? `, ${runData.totalUnworthy} dilewati (tidak layak)` : "");
  showToast(
    `${runData.totalImagesOk}/${runData.totalImages} gambar selesai diproses${skippedText} -- klik salah satu ` +
    `baris di bawah untuk mulai review/koreksi.`
  );
}

// -----------------------------------------------------------------------
// Koreksi massal (bulk) -- terapkan satu kelas ke banyak sel sekaligus,
// cocok buat kasus banyak sel yang salah diklasifikasi ke kelas yang sama
// (mis. banyak "Uncategorised" yang sebenarnya "Normal cell").
// -----------------------------------------------------------------------
function toggleSegSelectAll() {
  if (segSelectAllCells.checked) {
    segDetections.forEach((d) => segSelectedCellIds.add(d.id));
  } else {
    segSelectedCellIds.clear();
  }
  renderDetectionsList();
}

function doSegBulkApply() {
  if (segSelectedCellIds.size === 0) {
    showToast("Pilih minimal satu sel dulu (centang di samping tiap sel).");
    return;
  }
  const newIndex = parseInt(segBulkClassSelect.value, 10);
  const newLabel = segClassLabels[newIndex].label;
  segDetections.forEach((d) => {
    if (!segSelectedCellIds.has(d.id)) return;
    d.correctedClassIndex = newIndex;
    d.correctedClassLabel = newLabel;
  });
  const count = segSelectedCellIds.size;
  renderSegmentationOverlay();
  renderDetectionsList();
  updateClassSummaryFromDetections();
  btnSaveSegmentation.disabled = segDetections.length === 0;
  showToast(`${count} sel diubah ke kelas "${newLabel}". Jangan lupa klik "Simpan hasil".`);
}

// Alur "review by exception": dokter cuma perlu tandai sel yang SALAH (klik
// &cross; satu-satu), lalu sekali klik ini buat menandai eksplisit semua sel
// yang belum disentuh (doctorVerdict masih null) sebagai Benar. Sengaja
// TIDAK ada asumsi diam-diam "belum direview = benar" di tempat lain manapun
// (lihat updateSegTotalCellCount/Ringkasan per Pasien) -- ini satu-satunya
// jalan buat sel jadi "benar", dan itu pun lewat aksi eksplisit dokter,
// bukan default otomatis, biar datanya tetap bisa dipercaya kalau nanti
// dipakai buat evaluasi model.
function doSegMarkRestCorrect() {
  const unreviewed = segDetections.filter((d) => d.doctorVerdict === null || d.doctorVerdict === undefined);
  if (unreviewed.length === 0) {
    showToast("Semua sel sudah direview (Benar/Salah).");
    return;
  }
  unreviewed.forEach((d) => (d.doctorVerdict = "correct"));
  renderDetectionsList();
  showToast(`${unreviewed.length} sel yang belum direview ditandai Benar. Jangan lupa klik "Simpan hasil".`);
}

// -----------------------------------------------------------------------
// Status & konfigurasi model segmentasi (placeholder -- lihat catatan di
// app.py, belum ada inference model beneran yang terpasang)
// -----------------------------------------------------------------------
async function loadSegModelStatus() {
  try {
    const res = await fetch("/api/segmentation/model-status");
    const data = await res.json();
    segModelStatusText.textContent = data.message || "Status model tidak diketahui.";
    segModelPathInput.value = data.modelPath || "";
    document.getElementById("segModelOutputType").value = data.outputType || "single";
    // Selama model masih mock, statusnya harus mencolok di banner dan bar status.
    segModelBanner.textContent = data.usingMock
      ? "Model yang terpasang masih mock: kelas sel diisi acak untuk uji alur."
      : "";
    statusModel.textContent = data.usingMock ? "Model: mock, bukan model asli" : "Model: " + (data.modelPath || "terpasang");
    statusModel.classList.toggle("status-warn", !!data.usingMock);
    if (data.lowConfidenceThreshold) {
      segLowConfidenceThresholdInput.value = data.lowConfidenceThreshold;
      segLowConfidenceThreshold = data.lowConfidenceThreshold / 100;
    }
  } catch (e) {
    segModelStatusText.textContent = "Gagal memuat status model.";
    statusModel.textContent = "Model: status tidak diketahui";
  }
}

async function doSaveSegModelConfig() {
  btnSegSaveModelConfig.disabled = true;
  btnSegSaveModelConfig.textContent = "Menyimpan...";
  const res = await fetch("/api/segmentation/model-config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      modelPath: segModelPathInput.value.trim(),
      lowConfidenceThreshold: parseInt(segLowConfidenceThresholdInput.value, 10),
      outputType: document.getElementById("segModelOutputType").value,
    }),
  });
  const data = await res.json();
  btnSegSaveModelConfig.disabled = false;
  btnSegSaveModelConfig.textContent = "Simpan";
  if (!data.ok) {
    if (!data.offline) showError(data.message || "Gagal menyimpan konfigurasi model.");
    return;
  }
  if (data.lowConfidenceThreshold) {
    segLowConfidenceThresholdInput.value = data.lowConfidenceThreshold;
    segLowConfidenceThreshold = data.lowConfidenceThreshold / 100;
    // Langsung terapkan ke hasil yang lagi ditampilkan (kalau ada) biar badge
    // & garis putus-putus "confidence rendah" nggak perlu jalan ulang segmentasi.
    if (segDetections.length > 0) {
      renderSegmentationOverlay();
      renderDetectionsList();
    }
  }
  showToast("Konfigurasi model tersimpan.");
  loadSegModelStatus();
}

// -----------------------------------------------------------------------
// Shortcut keyboard buat koreksi cepat sel yang lagi aktif/dipilih
// -----------------------------------------------------------------------
window.addEventListener("keydown", (e) => {
  if (segmentationView.classList.contains("view-hidden") || isOverlayOpen()) return;
  const tag = document.activeElement ? document.activeElement.tagName : "";
  if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;

  if (e.key === "Escape" && segAddMode) {
    toggleSegAddMode();
    return;
  }
  if (segActiveCellId === null) return;
  const det = segDetections.find((d) => d.id === segActiveCellId);
  if (!det) return;

  if (e.key === "Delete" || e.key === "Backspace") {
    e.preventDefault();
    deleteDetection(segActiveCellId);
    return;
  }
  if (e.key >= "0" && e.key <= "9") {
    const idx = parseInt(e.key, 10);
    if (idx < segClassLabels.length) setDetClass(det, idx);
    return;
  }
  if (e.key === "b" || e.key === "B" || e.key === "s" || e.key === "S") {
    setDetVerdict(det, e.key.toLowerCase() === "b" ? "correct" : "incorrect");
    return;
  }
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    const ids = segDetections.map((d) => d.id);
    const curIdx = ids.indexOf(segActiveCellId);
    if (curIdx === -1) return;
    const nextIdx = Math.max(0, Math.min(ids.length - 1, curIdx + (e.key === "ArrowDown" ? 1 : -1)));
    setActiveCell(ids[nextIdx]);
    return;
  }
  if (e.key === "+" || e.key === "=") {
    e.preventDefault();
    resizeActiveCell(1.1);
    return;
  }
  if (e.key === "-" || e.key === "_") {
    e.preventDefault();
    resizeActiveCell(1 / 1.1);
  }
});

// -----------------------------------------------------------------------
// Inspektur sel: sel terpilih dengan tombol kelas dan verdict yang besar,
// supaya review bisa dilakukan di layar sentuh tanpa dropdown kecil.
// -----------------------------------------------------------------------
function setDetClass(det, idx) {
  det.correctedClassIndex = idx;
  det.correctedClassLabel = segClassLabels[idx].label;
  renderSegmentationOverlay();
  renderDetectionsList();
  updateClassSummaryFromDetections();
}

// Tekan verdict yang sama dua kali = batal (sama dengan tombol di daftar sel).
// Dari inspektur dan shortcut B/S, pilihan langsung pindah ke sel berikutnya
// supaya dokter cukup menekan S, S, B, ... tanpa memilih sel satu per satu.
// Kalau verdict dibatalkan, pilihan tetap di sel itu.
function setDetVerdict(det, verdict, advance = true) {
  det.doctorVerdict = det.doctorVerdict === verdict ? null : verdict;
  renderDetectionsList();
  if (!advance || !det.doctorVerdict) return;
  const next = segDetections[segDetections.indexOf(det) + 1];
  if (next) setActiveCell(next.id);
}

function renderInspector() {
  const total = segDetections.length;
  const reviewed = segDetections.filter((d) => d.doctorVerdict).length;
  const pct = total ? Math.round((reviewed / total) * 100) : 0;
  const progress = `
    <div class="review-progress">
      <div class="review-progress-text"><span>Direview</span><strong>${reviewed} dari ${total}</strong></div>
      <div class="focus-bar"><div class="focus-bar-fill review-fill" style="width:${pct}%"></div></div>
      ${total && reviewed < total ? '<button type="button" class="btn btn-block" data-action="rest" title="Tandai semua sel yang belum direview sebagai Benar">Tandai sisanya benar</button>' : ""}
    </div>`;
  const det = segDetections.find((d) => d.id === segActiveCellId);
  if (!det) {
    const hint = total ? "Ketuk sel di citra atau di daftar untuk mereview." : "Belum ada hasil segmentasi.";
    segInspector.innerHTML = `<div class="card-head"><h2>Sel terpilih</h2></div><p class="muted small">${hint}</p>${progress}`;
    return;
  }
  const n = segDetections.indexOf(det) + 1;
  const idx = currentClassIndex(det);
  const model = segClassLabels[det.classIndex];
  const lowConf = !det.manual && det.confidence < segLowConfidenceThreshold;
  const parts = correctedParts(det);
  const tags = [
    det.manual ? "ditambah dokter" : `yakin ${Math.round(det.confidence * 100)}%`,
    lowConf ? "keyakinan rendah" : "",
  ].filter(Boolean).join(", ");
  const doctorLine = parts.length
    ? `<div class="corrected-line"><span class="mark-dot"></span> Dikoreksi dokter (${parts.join(", ")}): <strong>${segClassLabels[idx] ? segClassLabels[idx].label : "-"}</strong></div>`
    : "";
  const attrs = det.correctedAttributes || det.attributes || null;
  const attrText = (a) =>
    a ? `ukuran ${a.ukuran || "tidak diketahui"}, warna ${a.warna || "tidak diketahui"}, bentuk ${a.bentuk.length ? a.bentuk.join(" + ") : "normal"}` : "";
  const modeToggle = `
    <div class="seg-toggle mode-toggle" role="radiogroup" aria-label="Mode label review">
      <button type="button" role="radio" class="seg-image-tab${segLabelMode === "single" ? " seg-image-tab-active" : ""}" aria-checked="${segLabelMode === "single"}" data-action="mode" data-mode="single">Satu kelas</button>
      <button type="button" role="radio" class="seg-image-tab${segLabelMode === "attributes" ? " seg-image-tab-active" : ""}" aria-checked="${segLabelMode === "attributes"}" data-action="mode" data-mode="attributes">Ukuran, bentuk, warna</button>
    </div>`;
  const cur = attrs || { ukuran: null, warna: "normokrom", bentuk: [] };
  const attrButtons = (key, values, multi) =>
    values
      .map((v) => {
        const on = multi ? cur.bentuk.includes(v) : cur[key] === v;
        const fromModel = det.attributes && (multi ? det.attributes.bentuk.includes(v) : det.attributes[key] === v);
        const changed = det.attributes && det.correctedAttributes && on !== fromModel;
        return `<button type="button" class="btn attr-btn${changed ? " attr-changed" : ""}" data-action="attr" data-key="${key}" data-value="${v}" aria-pressed="${on}" title="${fromModel ? "pilihan model" : ""}">${v}${fromModel ? " <small>(model)</small>" : ""}</button>`;
      })
      .join("");
  const attrPanel = segAttrVocab
    ? `
    ${det.attributes ? `<div class="muted small">Atribut dari model: ${attrText(det.attributes)}</div>` : ""}
    <div class="attr-group"><span class="group-label">Ukuran</span>${attrButtons("ukuran", segAttrVocab.ukuran)}<button type="button" class="btn attr-btn" data-action="attr" data-key="ukuran" data-value="" aria-pressed="${!cur.ukuran}">tidak diketahui</button></div>
    <div class="attr-group"><span class="group-label">Warna</span>${attrButtons("warna", segAttrVocab.warna)}</div>
    <div class="attr-group"><span class="group-label">Bentuk, boleh lebih dari satu (kosong = normal)</span>${attrButtons("bentuk", segAttrVocab.bentuk, true)}</div>
    <div class="small">Kelas turunan: <strong>${segClassLabels[idx] ? segClassLabels[idx].label : "-"}</strong></div>`
    : '<p class="muted small">Daftar atribut belum termuat.</p>';
  const classButtons = segClassLabels
    .map(
      (c) => `
      <button type="button" class="class-btn" data-action="class" data-index="${c.index}" aria-pressed="${c.index === idx}">
        <span class="seg-color-dot" style="background:${c.color}"></span>
        <span class="class-name">${c.label}</span>
        ${c.index < 10 ? `<kbd>${c.index}</kbd>` : ""}
      </button>`
    )
    .join("");
  segInspector.innerHTML = `
    <div class="card-head">
      <h2>Sel ${n} dari ${total}</h2>
      <div class="pager">
        <button type="button" class="btn btn-square" data-action="prev" aria-label="Sel sebelumnya">&lsaquo;</button>
        <button type="button" class="btn btn-square" data-action="next" aria-label="Sel berikutnya">&rsaquo;</button>
      </div>
    </div>
    <div class="cell-head">
      <canvas id="cellCrop" class="cell-crop" width="144" height="144" role="img" aria-label="Potongan citra sel ${n}, diperbesar"></canvas>
      <div class="muted small">Kelas dari model:<br /><strong>${det.manual ? "tidak ada (ditambah dokter)" : model ? model.label : "-"}</strong><br />${tags}${doctorLine}</div>
    </div>
    ${modeToggle}
    ${segLabelMode === "attributes" ? attrPanel : `<div class="class-grid" role="group" aria-label="Kelas sel">${classButtons}</div>`}
    <div class="verdict">
      <button type="button" class="btn verdict-ok" data-action="verdict" data-verdict="correct" aria-pressed="${det.doctorVerdict === "correct"}">Benar <kbd>B</kbd></button>
      <button type="button" class="btn verdict-bad" data-action="verdict" data-verdict="incorrect" aria-pressed="${det.doctorVerdict === "incorrect"}">Salah <kbd>S</kbd></button>
      <button type="button" class="btn" data-action="delete" title="Hapus deteksi ini (Delete)">Hapus</button>
    </div>
    ${progress}`;
  drawCellCrop(det);
}

// Potongan sel terpilih, diperbesar, dengan garis tepi sel berwarna kelas:
// dokter bisa menilai bentuk sel tanpa memperbesar seluruh citra.
let cropSourceImg = null;
function drawCellCrop(det) {
  const canvas = document.getElementById("cellCrop");
  if (!canvas || !segCurrentImageDataUrl) return;
  if (!cropSourceImg || cropSourceImg.dataset.src !== segCurrentImageDataUrl) {
    cropSourceImg = new Image();
    cropSourceImg.dataset.src = segCurrentImageDataUrl;
    cropSourceImg.onload = () => renderInspector();
    cropSourceImg.src = segCurrentImageDataUrl;
    return;
  }
  if (!cropSourceImg.complete) return;
  const [bx, by, bw, bh] = det.bbox;
  const side = Math.max(bw, bh) * 1.6; // margin supaya sel tetangga dan latar ikut terlihat
  const sx = bx + bw / 2 - side / 2;
  const sy = by + bh / 2 - side / 2;
  const ctx = canvas.getContext("2d");
  const k = canvas.width / side;
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(cropSourceImg, sx, sy, side, side, 0, 0, canvas.width, canvas.height);
  const color = segClassLabels[currentClassIndex(det)] ? segClassLabels[currentClassIndex(det)].color : "#fff";
  ctx.beginPath();
  det.mask.forEach(([x, y], i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, (x - sx) * k, (y - sy) * k));
  ctx.closePath();
  ctx.lineWidth = 2;
  ctx.strokeStyle = color;
  ctx.stroke();
}

function handleInspectorClick(e) {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  if (btn.dataset.action === "rest") {
    doSegMarkRestCorrect(); // tetap bisa dipakai walau belum ada sel terpilih
    return;
  }
  const det = segDetections.find((d) => d.id === segActiveCellId);
  if (!det) return;
  const action = btn.dataset.action;
  if (action === "mode") {
    segLabelMode = btn.dataset.mode;
    localStorage.setItem("adt-label-mode", segLabelMode);
    renderInspector();
    return;
  }
  if (action === "attr") {
    setDetAttribute(det, btn.dataset.key, btn.dataset.value);
    return;
  }
  if (action === "class") setDetClass(det, parseInt(btn.dataset.index, 10));
  else if (action === "verdict") setDetVerdict(det, btn.dataset.verdict);
  else if (action === "delete") deleteDetection(det.id);
  else if (action === "prev" || action === "next") {
    const i = segDetections.indexOf(det) + (action === "next" ? 1 : -1);
    if (i >= 0 && i < segDetections.length) setActiveCell(segDetections[i].id);
  }
}

// -----------------------------------------------------------------------
// Mode review "Ukuran, bentuk, warna" (F15) dan persiapan model multi-label.
// Atribut dokter disimpan di correctedAttributes; kelas turunannya (aturan
// resolve_class di attributes.py, dihitung server supaya satu sumber) menjadi
// kelas koreksi, sehingga hitungan, laporan, dan export tetap memakai satu kelas.
// -----------------------------------------------------------------------
let segLabelMode = localStorage.getItem("adt-label-mode") || "single";
let segAttrVocab = null; // {ukuran: [...], warna: [...], bentuk: [...]}

async function loadAttrVocab() {
  const res = await fetch("/api/segmentation/attributes");
  const data = await res.json();
  if (Array.isArray(data.ukuran)) segAttrVocab = data;
}

async function setDetAttribute(det, key, value) {
  const a = JSON.parse(JSON.stringify(det.correctedAttributes || det.attributes || { ukuran: null, warna: "normokrom", bentuk: [] }));
  if (key === "bentuk") a.bentuk = a.bentuk.includes(value) ? a.bentuk.filter((b) => b !== value) : [...a.bentuk, value];
  else a[key] = value || null;
  const res = await fetch("/api/segmentation/attributes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ attributes: a }),
  });
  const data = await res.json();
  if (!data.ok) {
    if (!data.offline) showError(data.message || "Gagal menghitung kelas turunan.");
    return;
  }
  det.correctedAttributes = data.attributes;
  setDetClass(det, data.classIndex);
}
