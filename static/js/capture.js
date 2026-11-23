// Layar Akuisisi: kamera, kualitas fokus, capture, simpan, riwayat sesi.
const cameraDot = document.getElementById("cameraDot");
const cameraLabel = document.getElementById("cameraLabel");
const cameraSelect = document.getElementById("cameraSelect");
const resolutionSelect = document.getElementById("resolutionSelect");
const btnConnectCamera = document.getElementById("btnConnectCamera");
const btnRefreshCameras = document.getElementById("btnRefreshCameras");
// null kalau OS server bukan Windows -- tombol ini disembunyikan server-side
// (lihat templates/index.html) karena dialog driver cuma didukung DirectShow.
const btnCameraSettings = document.getElementById("btnCameraSettings");

const btnCapture = document.getElementById("btnCapture");
const btnFolder = document.getElementById("btnFolder");
const btnSave = document.getElementById("btnSave");
const btnSummary = document.getElementById("btnSummary");
const btnCloseSummary = document.getElementById("btnCloseSummary");
const folderPathEl = document.getElementById("folderPath");
const summaryPanel = document.getElementById("summaryPanel");
const summaryBody = document.getElementById("summaryBody");

const streamBody = document.getElementById("streamBody");
const captureBody = document.getElementById("captureBody");
const captureBadge = document.getElementById("captureBadge");
const focusBadge = document.getElementById("focusBadge");
const blankBadge = document.getElementById("blankBadge");
const semanticBadge = document.getElementById("semanticBadge");
const edgeBadge = document.getElementById("edgeBadge");
const focusEdgeWarn = document.getElementById("focusEdgeWarn");
const focusCard = document.getElementById("focusCard");
const focusMap = document.getElementById("focusMap");
const focusStatusLine = document.getElementById("focusStatusLine");
const focusBarFill = document.getElementById("focusBarFill");
const focusDetail = document.getElementById("focusDetail");
const focusHint = document.getElementById("focusHint");
const clipLine = document.getElementById("clipLine");
const focusLiveToggle = document.getElementById("focusLiveToggle");
const btnResetPeak = document.getElementById("btnResetPeak");
const captureFilename = document.getElementById("captureFilename");
const captureCount = document.getElementById("captureCount");
const patientNameInput = document.getElementById("patientName");
const toast = document.getElementById("toast");
const galleryStrip = document.getElementById("galleryStrip");
const streamChip = document.getElementById("streamChip");
const saveHint = document.getElementById("saveHint");
const prereqCamera = document.getElementById("prereqCamera");

let selectedFolder = null;
let hasCapturedImage = false;
let lastSavedId = null; // ID pasien terakhir yang berhasil disimpan di sesi ini
let lastCapturedImage = null; // base64 PNG hasil capture terakhir (buat thumbnail galeri)
let lastSavedFullPath = null; // path lengkap hasil Save terakhir (buat "Kirim ke Segmentasi")
let currentCaptureSaved = false; // true kalau capture yang aktif sekarang sudah pernah di-save
let currentCaptureSavedAs = null; // nama file terakhir dari capture yang aktif sekarang
let currentCaptureFocus = null; // {status, relLow} kualitas fokus seluruh frame dari capture yang aktif (lihat /api/capture)
let focusPollBusy = false; // cegah request /api/focus/live menumpuk
let focusMapKey = null; // "ROWSxCOLS" peta tile yang sudah dibangun
let cameraFrozenShown = false;
const autoToggle = document.getElementById("autoToggle");
const autoPanel = document.getElementById("autoPanel");
let autoBusy = false; // sedang memotret+menyimpan otomatis, jangan picu lagi
let autoAccepted = 0;
let isCameraConnected = false; // dipakai checkCameraStatus() buat deteksi kamera dicabut fisik

async function loadCameras() {
  const res = await fetch("/api/cameras");
  const cameras = await res.json();
  if (!Array.isArray(cameras)) return; // server terputus, lihat fetch di common.js
  cameraSelect.innerHTML = "";
  if (cameras.length === 0) {
    const opt = document.createElement("option");
    opt.textContent = "Tidak ada kamera terdeteksi";
    cameraSelect.appendChild(opt);
    return;
  }
  cameras.forEach((cam) => {
    const opt = document.createElement("option");
    opt.value = cam.index;
    opt.textContent = cam.name;
    cameraSelect.appendChild(opt);
  });
}

// Dipakai bareng oleh connectCamera() (setelah klik Hubungkan) dan
// restoreCameraStatusIfConnected() (setelah reload halaman, kalau backend
// ternyata masih terhubung dari sebelumnya) -- biar UI "Aktif"-nya konsisten
// dari dua jalur berbeda ini.
function applyConnectedUI(selectedName, width, height) {
  const resText = width && height ? ` (${width}x${height})` : "";
  cameraDot.className = "dot dot-on";
  cameraLabel.textContent = "Aktif: " + selectedName + resText;
  streamBody.innerHTML = '<img src="/stream" alt="stream" />';
  btnCapture.disabled = false;
  if (btnCameraSettings) btnCameraSettings.disabled = false;
  isCameraConnected = true;
  focusCard.classList.remove("focus-card-hidden");
  mirrorFocusChip();
  updateSaveButtonState();
}

async function connectCamera() {
  const index = parseInt(cameraSelect.value || "0", 10);

  let width = null;
  let height = null;
  if (resolutionSelect.value) {
    const [w, h] = resolutionSelect.value.split("x").map(Number);
    width = w;
    height = h;
  }

  btnConnectCamera.disabled = true;
  btnConnectCamera.textContent = "Menghubungkan...";
  const res = await fetch("/api/camera/connect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ index, width, height }),
  });
  const data = await res.json();
  btnConnectCamera.disabled = false;
  btnConnectCamera.textContent = "Hubungkan";

  if (data.connected) {
    const selectedName = cameraSelect.options[cameraSelect.selectedIndex]
      ? cameraSelect.options[cameraSelect.selectedIndex].text
      : "index " + data.index;
    applyConnectedUI(selectedName, data.width, data.height);
    hideError("camera");
    saveSession();
  } else {
    cameraDot.className = "dot dot-off";
    cameraLabel.textContent = "Gagal menghubungkan kamera";
    if (btnCameraSettings) btnCameraSettings.disabled = true;
    isCameraConnected = false;
    updateSaveButtonState();
    if (data.offline) return;
    showError(
      (data.message || "Tidak bisa membuka kamera index " + index) +
        " Cek kabel USB dan pastikan kamera tidak dipakai aplikasi lain.",
      { label: "Coba hubungkan lagi", run: connectCamera },
      "camera"
    );
  }
}

function handleCameraDisconnected() {
  isCameraConnected = false;
  cameraDot.className = "dot dot-off";
  cameraLabel.textContent = "Kamera terputus (dicabut?)";
  streamBody.innerHTML =
    '<span class="placeholder-text">Kamera terputus.<br />Cek kabel USB, lalu tekan Hubungkan.</span>';
  btnCapture.disabled = true;
  if (btnCameraSettings) btnCameraSettings.disabled = true;
  focusCard.classList.add("focus-card-hidden");
  streamChip.classList.add("view-hidden");
  focusOverlay.classList.add("view-hidden");
  updateSaveButtonState();
  showError(
    "Koneksi ke kamera terputus. Cek kabel USB kamera, lalu sambungkan ulang.",
    { label: "Sambungkan ulang kamera", run: connectCamera },
    "camera"
  );
}

async function checkCameraStatus() {
  if (!isCameraConnected) return; // nggak perlu polling kalau memang belum/nggak lagi connect
  try {
    const res = await fetch("/api/camera/status");
    const data = await res.json();
    if (data.offline) return; // galat koneksi ke server sudah ditangani di common.js
    if (!data.connected) {
      handleCameraDisconnected();
      return;
    }
    // Stream beku: tampilkan sekali per kejadian, hapus sendiri bila pulih.
    if (data.frozen && !cameraFrozenShown) {
      cameraFrozenShown = true;
      showError(
        "Gambar kamera tidak berubah beberapa detik (stream beku). Cabut lalu pasang lagi kabel USB kamera, kemudian sambungkan ulang.",
        { label: "Sambungkan ulang kamera", run: connectCamera },
        "frozen"
      );
    } else if (!data.frozen && cameraFrozenShown) {
      cameraFrozenShown = false;
      hideError("frozen");
    }
  } catch (e) {
    // Abaikan error jaringan sesaat, biar nggak salah nganggep disconnect
    // gara-gara satu request gagal doang.
  }
}

// Dipanggil sekali di awal (setelah loadCameras() ngisi dropdown) -- kalau
// server ternyata masih ada koneksi kamera aktif dari sebelum halaman
// di-reload (mis. Flask debug-reload, atau user cuma reload tab tanpa
// server-nya direstart), UI ikut disinkronkan tanpa user harus klik
// Hubungkan lagi secara manual.
async function restoreCameraStatusIfConnected() {
  try {
    const res = await fetch("/api/camera/status");
    const data = await res.json();
    if (!data.connected || data.index === null || data.index === undefined) return;

    cameraSelect.value = String(data.index);
    const selectedName = cameraSelect.options[cameraSelect.selectedIndex]
      ? cameraSelect.options[cameraSelect.selectedIndex].text
      : "index " + data.index;
    applyConnectedUI(selectedName, data.width, data.height);
  } catch (e) {
    // Server belum siap/nggak bisa dihubungi sesaat -- biarkan UI default
    // (belum connect), user masih bisa klik Hubungkan manual seperti biasa.
  }
}

async function openCameraSettings() {
  btnCameraSettings.disabled = true;
  btnCameraSettings.textContent = "Menunggu dialog ditutup...";
  const res = await fetch("/api/camera/settings", { method: "POST" });
  const data = await res.json();
  btnCameraSettings.disabled = false;
  btnCameraSettings.textContent = "Pengaturan driver";

  if (!data.ok) {
    showError(data.message || "Gagal membuka dialog pengaturan kamera.");
    return;
  }
  const selectedName = cameraSelect.options[cameraSelect.selectedIndex]
    ? cameraSelect.options[cameraSelect.selectedIndex].text
    : "";
  const resText = data.width && data.height ? ` (${data.width}x${data.height})` : "";
  cameraLabel.textContent = "Aktif: " + selectedName + resText;
  showToast("Resolusi kamera saat ini: " + data.width + "x" + data.height);
}

// -----------------------------------------------------------------------
// Kualitas fokus seluruh frame (Tenengrad per tile, relatif terhadap puncak
// tile itu sendiri) -- lihat FocusTracker di app.py. Nilai mentah antar
// lapang pandang tidak sebanding, jadi yang ditampilkan selalu % dari puncak
// yang teramati sejak fokus mulai diputar di lapang pandang yang sama.
// -----------------------------------------------------------------------
const FOCUS_STATUS_LABEL = { baik: "Baik", sedang: "Sedang", buram: "Buram" };
const FOCUS_STATUS_STATUS_CLASS = {
  baik: "focus-status-good",
  sedang: "focus-status-mid",
  buram: "focus-status-bad",
};
const FOCUS_STATUS_BADGE_CLASS = {
  baik: "badge-focus-good",
  sedang: "badge-focus-mid",
  buram: "badge-focus-bad",
};

function buildFocusMap(rows, cols) {
  focusMap.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
  focusMap.innerHTML = "";
  for (let i = 0; i < rows * cols; i++) {
    const cell = document.createElement("div");
    cell.className = "focus-cell";
    focusMap.appendChild(cell);
  }
  focusMapKey = `${rows}x${cols}`;
}

// 40% dari puncak = merah, 100% = hijau
function relToColor(rel) {
  const t = Math.max(0, Math.min(1, (rel - 0.4) / 0.6));
  return `hsl(${Math.round(t * 120)}, 65%, 48%)`;
}

function renderFocusMap(q) {
  renderFocusOverlay(q);
  if (!q || !q.valid) return;
  if (focusMapKey !== `${q.rows}x${q.cols}`) buildFocusMap(q.rows, q.cols);
  const cells = focusMap.children;
  for (let r = 0; r < q.rows; r++) {
    for (let c = 0; c < q.cols; c++) {
      const cell = cells[r * q.cols + c];
      const raw = q.tiles[r][c];
      const rel = q.tilesRel[r][c];
      if (raw === null) {
        cell.className = "focus-cell focus-cell-empty";
        cell.style.background = "";
        cell.title = "Tile kosong (tanpa sel), tidak dihitung";
      } else if (!q.confirmed || rel === null) {
        // Belum ada puncak terkonfirmasi: jangan beri warna yang menyiratkan penilaian.
        cell.className = "focus-cell focus-cell-neutral";
        cell.style.background = "";
        cell.title = `Tenengrad ${raw}`;
      } else {
        cell.className = "focus-cell";
        cell.style.background = relToColor(rel);
        cell.title = `Tenengrad ${raw} (${Math.round(rel * 100)}% dari puncak tile ini)`;
      }
    }
  }
}

// Peringatan pinggir lebih lemah dari tengah (rasio Tenengrad tepi/tengah di
// bawah ambang). Petunjuk satu-frame saja, tidak mengubah status fokus: status
// hanya menilai setelan fokus relatif terhadap puncak tiap tile, jadi pinggir
// yang buram bawaan tidak terlihat olehnya.
const focusOverlay = document.getElementById("focusOverlay");
const focusOverlayToggle = document.getElementById("focusOverlayToggle");

function renderFocusOverlay(q) {
  const img = streamBody.querySelector("img");
  if (!focusOverlayToggle.checked || !img || !q || !q.valid || !isCameraConnected) {
    focusOverlay.classList.add("view-hidden");
    return;
  }
  const wrap = focusOverlay.parentElement.getBoundingClientRect();
  const box = img.getBoundingClientRect();
  Object.assign(focusOverlay.style, {
    left: box.left - wrap.left + "px",
    top: box.top - wrap.top + "px",
    width: box.width + "px",
    height: box.height + "px",
    gridTemplateColumns: `repeat(${q.cols}, 1fr)`,
    gridTemplateRows: `repeat(${q.rows}, 1fr)`,
  });
  let cells = "";
  for (let r = 0; r < q.rows; r++) {
    for (let c = 0; c < q.cols; c++) {
      const raw = q.tiles[r][c];
      const rel = q.tilesRel[r][c];
      let bg = "transparent"; // tile kosong (tanpa sel) tidak dinilai
      if (raw !== null && (!q.confirmed || rel === null)) bg = "rgba(255, 255, 255, 0.12)";
      else if (raw !== null) {
        const t = Math.max(0, Math.min(1, (rel - 0.4) / 0.6));
        bg = `hsla(${Math.round(t * 120)}, 65%, 48%, 0.38)`;
      }
      cells += `<span style="background:${bg}"></span>`;
    }
  }
  focusOverlay.innerHTML = cells;
  focusOverlay.classList.remove("view-hidden");
}

function edgeWarnText(q) {
  return (
    `Pinggir frame lebih lemah dari tengah (tepi/tengah ${q.edgeRatio.toFixed(2)}). ` +
    `Periksa pojok-pojok gambar; bisa karena pinggir kurang fokus, atau sel di pinggir lebih jarang.`
  );
}

function renderFocusStatus(q) {
  if (!q || !q.valid) {
    focusStatusLine.className = "focus-status focus-status-neutral";
    focusStatusLine.textContent = "Tidak ada sel terdeteksi di frame";
    focusBarFill.style.width = "0";
    focusDetail.textContent = "";
    focusEdgeWarn.className = "focus-warn focus-warn-hidden";
    focusHint.textContent = "Frame kosong/seragam atau lensa tertutup.";
    mirrorFocusChip();
    return;
  }
  if (q.edgeWarn) {
    // Versi pendek di panel (ruang sempit); penjelasan lengkap di tooltip.
    focusEdgeWarn.textContent = "Pinggir lebih lemah dari tengah. Cek pojok gambar dan kemiringan preparat.";
    focusEdgeWarn.title = edgeWarnText(q);
    focusEdgeWarn.className = "focus-warn";
  } else {
    focusEdgeWarn.className = "focus-warn focus-warn-hidden";
  }
  if (q.status) {
    const pct = Math.round(q.relLow * 100);
    focusStatusLine.className = "focus-status " + FOCUS_STATUS_STATUS_CLASS[q.status];
    focusStatusLine.textContent = `Fokus ${FOCUS_STATUS_LABEL[q.status]} (${pct}% dari puncak)`;
    focusBarFill.style.width = pct + "%";
    focusBarFill.style.background = relToColor(q.relLow);
    focusHint.textContent = "";
  } else {
    focusStatusLine.className = "focus-status focus-status-neutral";
    focusStatusLine.textContent = "Puncak fokus belum terkonfirmasi";
    focusBarFill.style.width = "0";
    focusHint.textContent =
      "Putar fokus sedikit melewati titik paling tajam, lalu kembali, supaya ada pembanding.";
  }
  if (q.changed) focusHint.textContent = "Lapang pandang berganti, referensi puncak direset otomatis.";
  const fmt = (v) => (v === null || v === undefined ? "-" : v.toFixed(1));
  const ratio = q.edgeRatio === null || q.edgeRatio === undefined ? "-" : q.edgeRatio.toFixed(2);
  focusDetail.textContent =
    `Tenengrad median tile ${fmt(q.median)} · tengah ${fmt(q.center)} · tepi ${fmt(q.edge)} ` +
    `(tepi/tengah ${ratio}) · tile berisi sel ${Math.round(q.validFrac * 100)}%` +
    (q.laplacian === undefined ? "" : ` · Laplacian ${q.laplacian.toFixed(1)}`);
  mirrorFocusChip();
}

// Status fokus ditampilkan juga di atas stream, supaya operator tidak perlu
// memindahkan pandangan saat memutar fokus.
function mirrorFocusChip() {
  streamChip.textContent = focusStatusLine.textContent;
  streamChip.className = "stream-chip " + focusStatusLine.className.replace("focus-status ", "");
}

function renderClipLine(state) {
  const text = {
    loading: "Semantik CLIP: memuat model...",
    ready: "Semantik CLIP: aktif (dihitung saat Capture)",
    error: "Semantik CLIP: gagal dimuat, lihat konsol server",
  }[state];
  clipLine.textContent = text || "";
}

async function pollFocusLive() {
  if (focusPollBusy || !isCameraConnected || !focusLiveToggle.checked || document.hidden) return;
  if (captureView.classList.contains("view-hidden")) return;
  focusPollBusy = true;
  try {
    const res = await fetch(autoToggle.checked ? "/api/focus/live?auto=1" : "/api/focus/live");
    const data = await res.json();
    if (data.ok) {
      renderFocusMap(data.quality);
      renderFocusStatus(data.quality);
      renderClipLine(data.clipState);
      if (data.auto && autoToggle.checked) handleAutoGates(data.auto);
    }
  } catch (e) {
    // Abaikan error sesaat, polling berikutnya akan mencoba lagi.
  } finally {
    focusPollBusy = false;
  }
}

// -----------------------------------------------------------------------
// Capture otomatis tingkat 1 (UC-13). Gerbang dinilai server di setiap poll
// fokus (autocapture.py); di sini hanya prasyarat sesi dan pemicu simpan.
// -----------------------------------------------------------------------
function autoBlocker() {
  if (!patientNameInput.value.trim()) return "Isi inisial pasien dulu.";
  if (!selectedFolder) return "Pilih lokasi simpan dulu.";
  if (hasCapturedImage && !currentCaptureSaved) return "Simpan atau ambil ulang citra manual yang belum tersimpan dulu.";
  return null;
}

function handleAutoGates(auto) {
  const blocker = autoBlocker();
  const title = document.getElementById("autoTitle");
  const failing = auto.gates.find((g) => g.ok === false);
  title.className = "auto-title" + (auto.ready && !blocker ? " auto-ready" : "");
  title.textContent = blocker || (auto.ready ? "Memotret..." : "Menunggu: " + failing.label.toLowerCase());
  document.getElementById("autoGates").innerHTML = auto.gates
    .map((g) => {
      const cls = g.ok === true ? "gate-ok" : g.ok === false ? "gate-fail" : "gate-wait";
      const mark = g.ok === true ? "&check;" : g.ok === false ? "&times;" : "&ndash;";
      const detail = g.detail ? `<span class="gate-detail">${g.detail}</span>` : "";
      return `<li class="${cls}"><span class="gate-mark">${mark}</span><span>${g.label}</span>${detail}</li>`;
    })
    .join("");
  if (auto.ready && !blocker && !autoBusy) autoCaptureAndSave();
}

async function autoCaptureAndSave() {
  autoBusy = true;
  try {
    await doCapture();
    if (!hasCapturedImage || currentCaptureSaved) return;
    await doSave("otomatis");
    if (currentCaptureSaved) {
      autoAccepted += 1;
      document.getElementById("autoAccepted").textContent = autoAccepted;
      galleryStrip.lastElementChild.classList.add("gallery-auto");
    }
  } finally {
    autoBusy = false;
  }
}

function setAutoMode(on) {
  autoToggle.checked = on;
  autoPanel.classList.toggle("view-hidden", !on);
  if (on) {
    focusLiveToggle.checked = true; // gerbang dinilai lewat poll fokus live
    document.getElementById("autoTitle").textContent = "Memeriksa lapang...";
    document.getElementById("autoGates").innerHTML = "";
  }
}

// -----------------------------------------------------------------------
// Cek perangkat saat menyala (F5) dan penjaga penyimpanan (F11)
// -----------------------------------------------------------------------
const statusDisk = document.getElementById("statusDisk");

function formatBytes(n) {
  return n >= 1024 ** 3 ? (n / 1024 ** 3).toFixed(1) + " GB" : Math.round(n / 1024 ** 2) + " MB";
}

async function refreshSystemStatus() {
  const res = await fetch("/api/system/status?folder=" + encodeURIComponent(selectedFolder || ""));
  const data = await res.json();
  if (!data.ok) return null;
  if (data.disk) {
    statusDisk.textContent = `Penyimpanan: ${formatBytes(data.disk.free)} tersisa` + (data.disk.low ? ", hampir penuh" : "");
    statusDisk.classList.toggle("status-warn", data.disk.low);
  }
  return data;
}

async function showStartupCheckIfNeeded() {
  const data = await refreshSystemStatus();
  if (!data || localStorage.getItem("adt-boot-checked") === data.bootId) return;
  const when = new Date(data.time).toLocaleString("id-ID", { dateStyle: "full", timeStyle: "short" });
  const cams = [...cameraSelect.options].filter((o) => o.value !== "").length;
  const rows = [
    ["Jam perangkat", when + (data.clockSuspect ? " (kemungkinan salah)" : ""), data.clockSuspect],
    ["Kamera", cams ? `${cams} terdeteksi` : "Tidak ada kamera terdeteksi. Cek kabel USB.", !cams],
    ["Penyimpanan", data.disk ? `${formatBytes(data.disk.free)} tersisa` + (data.disk.low ? ", hampir penuh" : "") : "Tidak terbaca", !data.disk || data.disk.low],
  ];
  document.getElementById("startupList").innerHTML = rows
    .map(([k, v, warn]) => `<dt>${k}</dt><dd class="${warn ? "check-warn" : ""}">${v}</dd>`)
    .join("");
  document.getElementById("startupClockHelp").classList.toggle("view-hidden", !data.clockSuspect);
  const dlg = document.getElementById("startupDialog");
  document.getElementById("btnStartupOk").onclick = () => {
    localStorage.setItem("adt-boot-checked", data.bootId);
    dlg.close();
  };
  const closed = new Promise((resolve) => dlg.addEventListener("close", resolve, { once: true }));
  document.getElementById("btnClockWrong").onclick = () =>
    document.getElementById("startupClockHelp").classList.remove("view-hidden");
  dlg.showModal();
  await closed; // pemulihan sesi ditawarkan sesudah cek perangkat selesai
}

async function resetFocusPeak() {
  try {
    await fetch("/api/focus/reset-peak", { method: "POST" });
  } catch (e) {
    return;
  }
  focusHint.textContent = "Referensi puncak direset.";
}

function renderCaptureFocusBadge(data) {
  const q = data.quality;
  const legacy = `Variance Laplacian (metode lama): ${data.focusScore} (${data.focusLabel})`;
  if (!q || !q.valid) {
    // Analisis per tile gagal/kosong: pakai skor lama sebagai cadangan.
    currentCaptureFocus = null;
    edgeBadge.textContent = "";
    edgeBadge.className = "badge badge-hidden";
    focusBadge.textContent =
      data.focusLabel === "Baik"
        ? `Fokus: Baik (${data.focusScore})`
        : `Fokus: Buram (${data.focusScore})`;
    focusBadge.className =
      "badge " + (data.focusLabel === "Baik" ? "badge-focus-good" : "badge-focus-bad");
    focusBadge.title = legacy;
    return;
  }
  currentCaptureFocus = { status: q.status, relLow: q.relLow };
  if (q.status) {
    focusBadge.textContent = `Fokus ${FOCUS_STATUS_LABEL[q.status]}: ${Math.round(q.relLow * 100)}% puncak`;
    focusBadge.className = "badge " + FOCUS_STATUS_BADGE_CLASS[q.status];
  } else {
    focusBadge.textContent = "Fokus: puncak belum terkonfirmasi";
    focusBadge.className = "badge badge-focus-neutral";
  }
  focusBadge.title =
    `Tenengrad median tile ${q.median.toFixed(1)}, area terburuk (P25) ${q.low.toFixed(1)}\n` + legacy;
  if (q.edgeWarn) {
    edgeBadge.textContent = `Pinggir lemah (${q.edgeRatio.toFixed(2)})`;
    edgeBadge.className = "badge badge-focus-mid";
    edgeBadge.title = edgeWarnText(q);
  } else {
    edgeBadge.textContent = "";
    edgeBadge.className = "badge badge-hidden";
  }
  renderFocusMap(q);
  renderFocusStatus(q);
}

function renderSemanticBadge(data) {
  const s = data.semantic;
  if (s) {
    semanticBadge.textContent =
      `Kepadatan CLIP: ${Math.round(s.kepadatan * 100)}% · Gabungan v2: ${Math.round(s.gabungan_v2 * 100)}%`;
    semanticBadge.className = "badge badge-semantic";
    semanticBadge.title =
      `Skor semantik CLIP (eksperimen, belum divalidasi dokter)\n` +
      `kepadatan ${s.kepadatan.toFixed(3)} · gabungan_v2 ${s.gabungan_v2.toFixed(3)} · norma ${s.norm.toFixed(2)}\n` +
      `${s.model}, ${s.crops} crop seluruh frame`;
  } else if (data.clipState === "loading") {
    semanticBadge.textContent = "CLIP: memuat model...";
    semanticBadge.className = "badge badge-focus-neutral";
    semanticBadge.title = "";
  } else if (data.clipState === "error") {
    semanticBadge.textContent = "CLIP: error";
    semanticBadge.className = "badge badge-focus-bad";
    semanticBadge.title = "Lihat konsol server";
  } else {
    semanticBadge.textContent = "";
    semanticBadge.className = "badge badge-hidden";
  }
}

let currentCaptureId = null; // nomor capture yang sedang tampil, untuk membuang skor CLIP yang terlambat

async function fetchCaptureClip(captureId) {
  try {
    const res = await fetch("/api/capture/clip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ captureId }),
    });
    const data = await res.json();
    if (captureId !== currentCaptureId) return;
    if (data.ok && data.blank) {
      semanticBadge.textContent = "CLIP: frame kosong, dilewati";
      semanticBadge.className = "badge badge-focus-neutral";
      semanticBadge.title = "Frame hitam/seragam: skor CLIP tidak bermakna sehingga tidak dihitung dan tidak dicatat di log.";
    } else if (data.ok) {
      renderSemanticBadge(data);
    } else if (!data.stale) {
      renderSemanticBadge({ semantic: null, clipState: "error" });
    }
  } catch (e) {
    if (captureId === currentCaptureId) renderSemanticBadge({ semantic: null, clipState: "error" });
  }
}

async function doCapture() {
  // Citra yang belum disimpan tidak boleh hilang diam-diam (mis. Spasi tertekan
  // tidak sengaja sebelum Simpan).
  if (hasCapturedImage && !currentCaptureSaved) {
    const choice = await showChoiceModal(
      "Citra sebelumnya belum disimpan. Kalau mengambil citra baru, citra itu hilang.",
      [
        { label: "Batal", value: null },
        { label: "Buang dan ambil baru", value: "discard" },
        { label: "Simpan dulu, lalu ambil", value: "save", primary: true },
      ]
    );
    if (!choice) return;
    if (choice === "save") {
      if (btnSave.disabled) {
        showToast(saveHint.textContent || "Citra belum bisa disimpan.");
        return;
      }
      await doSave();
      if (!currentCaptureSaved) return;
    }
  }
  const res = await fetch("/api/capture", { method: "POST" });
  const data = await res.json();
  if (!data.ok) {
    if (!data.offline) showError(data.message || "Gagal mengambil citra.", null, "capture");
    return;
  }
  hideError("capture");
  // "Kirim ke analisis" mengirim citra tersimpan terakhir; begitu ada capture
  // baru yang belum disimpan, matikan supaya yang terkirim tidak tertukar.
  btnSendToSegmentation.disabled = true;
  captureBody.innerHTML = `<img src="data:image/png;base64,${data.image}" alt="hasil capture" />`;
  captureBadge.textContent = "Belum Tersimpan";
  captureBadge.className = "badge badge-unsaved";
  captureFilename.textContent = "";
  hasCapturedImage = true;
  lastCapturedImage = data.image;
  currentCaptureSaved = false;
  currentCaptureSavedAs = null;

  renderCaptureFocusBadge(data);
  currentCaptureId = data.captureId;
  if (data.clipState === "ready") {
    // Skor CLIP lambat (~1 dtk), jadi diminta terpisah setelah gambar tampil.
    semanticBadge.textContent = "CLIP: menghitung...";
    semanticBadge.className = "badge badge-focus-neutral";
    semanticBadge.title = "";
    fetchCaptureClip(data.captureId);
  } else {
    renderSemanticBadge(data);
  }

  if (data.blankWarning) {
    blankBadge.textContent = "Kosong/Seragam";
    blankBadge.className = "badge badge-blank-warning";
  } else {
    blankBadge.textContent = "";
    blankBadge.className = "badge badge-hidden";
  }

  updateSaveButtonState();
}

async function doSelectFolder() {
  btnFolder.disabled = true;
  btnFolder.textContent = "Memilih...";
  const res = await fetch("/api/select-folder", { method: "POST" });
  btnFolder.disabled = false;
  btnFolder.textContent = "Lokasi simpan";
  const data = await res.json();
  if (!data.ok) return;
  selectedFolder = data.path;
  folderPathEl.textContent = selectedFolder;
  folderPathEl.title = selectedFolder;
  btnSummary.disabled = false;
  updateSaveButtonState();
  saveSession();
  loadFolderSummary();
  refreshSystemStatus();
}

// Riwayat sesi: tiap item menyimpan gambar hasil capture (resolusi asli kamera,
// bukan versi yang diperkecil oleh pilihan resolusi saat Save) plus ringkasan
// badge kualitas saat disimpan, supaya bisa dipreview lagi dan dibandingkan.
const galleryEntries = [];
let previewIndex = -1;

const imagePreview = document.getElementById("imagePreview");
const imagePreviewBody = document.getElementById("imagePreviewBody");
const imagePreviewImg = document.getElementById("imagePreviewImg");
const imagePreviewTitle = document.getElementById("imagePreviewTitle");
const imagePreviewInfo = document.getElementById("imagePreviewInfo");
const btnClosePreview = document.getElementById("btnClosePreview");
const btnPreviewPrev = document.getElementById("btnPreviewPrev");
const btnPreviewNext = document.getElementById("btnPreviewNext");

function captureInfoSnapshot() {
  return [focusBadge, edgeBadge, semanticBadge]
    .map((el) => el.textContent.trim())
    .filter(Boolean)
    .join(" · ");
}

function addToGallery(filename, thumbnailBase64) {
  const empty = galleryStrip.querySelector(".gallery-empty");
  if (empty) empty.remove();

  const index = galleryEntries.length;
  galleryEntries.push({ filename, image: thumbnailBase64, info: captureInfoSnapshot() });

  const item = document.createElement("div");
  item.className = "gallery-item";
  item.tabIndex = 0;
  item.title = "Klik untuk preview";
  item.innerHTML = `
    <img src="data:image/png;base64,${thumbnailBase64}" alt="${filename}" />
    <div class="gallery-label" title="${filename}">${filename}</div>
  `;
  item.addEventListener("click", () => openImagePreview(index));
  item.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    // Jangan sampai Enter di sini ikut memicu shortcut Save.
    e.preventDefault();
    e.stopPropagation();
    openImagePreview(index);
  });
  galleryStrip.appendChild(item);
  galleryStrip.scrollLeft = galleryStrip.scrollWidth;
}

function isImagePreviewOpen() {
  return !imagePreview.classList.contains("modal-hidden");
}

function openImagePreview(index) {
  const entry = galleryEntries[index];
  if (!entry) return;
  previewIndex = index;
  imagePreviewImg.classList.remove("image-preview-zoomed");
  imagePreviewImg.src = "data:image/png;base64," + entry.image;
  imagePreviewBody.scrollTop = 0;
  imagePreviewBody.scrollLeft = 0;
  imagePreviewTitle.textContent = `${entry.filename}  (${index + 1}/${galleryEntries.length})`;
  imagePreviewInfo.textContent = entry.info;
  btnPreviewPrev.disabled = index === 0;
  btnPreviewNext.disabled = index === galleryEntries.length - 1;
  imagePreview.classList.remove("modal-hidden");
}

function closeImagePreview() {
  imagePreview.classList.add("modal-hidden");
  imagePreviewImg.src = "";
  previewIndex = -1;
}

function stepImagePreview(delta) {
  const next = previewIndex + delta;
  if (next >= 0 && next < galleryEntries.length) openImagePreview(next);
}

// Info lengkap (ukuran piksel + hint zoom) baru diketahui setelah gambar termuat.
imagePreviewImg.addEventListener("load", () => {
  if (!isImagePreviewOpen() || previewIndex < 0) return;
  const entry = galleryEntries[previewIndex];
  const dims = `${imagePreviewImg.naturalWidth}x${imagePreviewImg.naturalHeight}`;
  imagePreviewInfo.textContent =
    (entry.info ? entry.info + " · " : "") + dims + " · klik gambar untuk zoom 100%";
});
imagePreviewImg.addEventListener("click", () => {
  imagePreviewImg.classList.toggle("image-preview-zoomed");
});
imagePreview.addEventListener("click", (e) => {
  if (e.target === imagePreview) closeImagePreview(); // klik area gelap di luar kotak
});
btnClosePreview.addEventListener("click", closeImagePreview);
btnPreviewPrev.addEventListener("click", () => stepImagePreview(-1));
btnPreviewNext.addEventListener("click", () => stepImagePreview(1));

// Didaftarkan lebih awal dari shortcut lain (Spasi = Capture, Enter = Save,
// shortcut Segmentasi) supaya selama preview terbuka tombol-tombol itu tidak
// ikut bereaksi.
window.addEventListener("keydown", (e) => {
  if (!isImagePreviewOpen()) return;
  e.stopImmediatePropagation();
  if (e.key === "Escape") closeImagePreview();
  else if (e.key === "ArrowLeft") stepImagePreview(-1);
  else if (e.key === "ArrowRight") stepImagePreview(1);
  if (e.key === " " || e.code === "Space") e.preventDefault(); // cegah halaman ikut scroll
});

let summaryDismissed = false; // true kalau user sengaja nutup panel ringkasan

let folderSummaryCache = []; // [{id, count}] dari ringkasan folder terakhir

// Sama dengan utils.safe_slug di server: nama file memakai bentuk ini.
function slugOf(name) {
  return name.trim().toLowerCase().replace(/ /g, "-").replace(/[^a-z0-9-]/g, "") || "pasien";
}

// UC-01: kalau pasien ini sudah punya citra di folder, sebutkan supaya
// operator tahu sesi ini melanjutkan, bukan pasien baru.
function renderPatientExisting() {
  const el = document.getElementById("patientExisting");
  const name = patientNameInput.value.trim();
  if (!name || !selectedFolder) {
    el.textContent = "";
    return;
  }
  const entry = folderSummaryCache.find((s) => s.id === slugOf(name));
  el.textContent = entry
    ? `Melanjutkan: sudah ada ${entry.count} citra untuk ${entry.id} di folder ini.`
    : "Pasien baru di folder ini.";
}

// UC-01/K-C6: pengaturan sesi diingat di browser dan dipulihkan saat halaman
// dibuka lagi (mis. setelah listrik padam).
function saveSession() {
  localStorage.setItem(
    "adt-session",
    JSON.stringify({
      patient: patientNameInput.value.trim(),
      folder: selectedFolder,
      resolution: resolutionSelect.value,
      camera: cameraSelect.value,
    })
  );
}

async function restoreSession() {
  let s;
  try {
    s = JSON.parse(localStorage.getItem("adt-session") || "null");
  } catch (e) {
    s = null;
  }
  if (!s) return;
  patientNameInput.value = s.patient || "";
  if (s.resolution !== undefined) resolutionSelect.value = s.resolution;
  if (s.camera && !isCameraConnected && [...cameraSelect.options].some((o) => o.value === s.camera)) {
    cameraSelect.value = s.camera;
  }
  if (s.folder) {
    selectedFolder = s.folder;
    folderPathEl.textContent = s.folder;
    folderPathEl.title = s.folder;
    btnSummary.disabled = false;
    await loadFolderSummary({ forceShow: false, show: false });
    if (!selectedFolder) showToast("Folder simpan sesi sebelumnya tidak ditemukan lagi. Pilih lokasi simpan.");
  }
  updateSaveButtonState();
  renderPatientExisting();
}

// UC-10: citra yang belum disimpan saat aplikasi tertutup disalin server ke
// disk; tawarkan untuk memulihkannya.
async function offerCaptureRecovery() {
  const data = await (await fetch("/api/recovery/capture")).json();
  if (!data.exists || hasCapturedImage) return;
  const when = data.time ? new Date(data.time).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" }) : "";
  const action = await showChoiceModal(
    `Ada citra yang belum disimpan dari sesi sebelumnya (diambil ${when}). Pulihkan supaya bisa disimpan?`,
    [
      { label: "Buang", value: "discard" },
      { label: "Pulihkan", value: "restore", primary: true },
    ]
  );
  const res = await fetch("/api/recovery/capture", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  const r = await res.json();
  if (action !== "restore" || !r.ok) return;
  captureBody.innerHTML = `<img src="data:image/png;base64,${r.image}" alt="citra dipulihkan" />`;
  captureBadge.textContent = "Belum Tersimpan";
  captureBadge.className = "badge badge-unsaved";
  captureFilename.textContent = "Dipulihkan dari sesi sebelumnya" + (when ? ` (${when})` : "");
  hasCapturedImage = true;
  lastCapturedImage = r.image;
  currentCaptureSaved = false;
  currentCaptureSavedAs = null;
  currentCaptureFocus = r.quality && r.quality.valid ? { status: r.quality.status, relLow: r.quality.relLow } : null;
  updateSaveButtonState();
  switchTab("capture");
}

async function loadFolderSummary(options = {}) {
  const forceShow = options.forceShow !== false; // default true
  if (!selectedFolder) return;
  const res = await fetch("/api/folder-summary?folder=" + encodeURIComponent(selectedFolder));
  const data = await res.json();
  folderSummaryCache = data.ok ? data.summary : [];
  if (!data.ok && !data.offline && options.forceShow === false) {
    // Folder sesi lama sudah tidak ada: lupakan, jangan tampilkan panel.
    selectedFolder = null;
    folderPathEl.textContent = "Belum dipilih";
    btnSummary.disabled = true;
    saveSession();
    renderPatientExisting();
    return;
  }
  renderPatientExisting();
  if (!data.ok) {
    summaryBody.innerHTML = `<div class="summary-row">${data.message || "Gagal memuat ringkasan."}</div>`;
  } else if (data.summary.length === 0) {
    summaryBody.innerHTML = `<div class="summary-row">Belum ada gambar tersimpan di folder ini.</div>`;
  } else {
    const rows = data.summary
      .map((s) => `<div class="summary-row"><span>${s.id}</span><span>${s.count} gambar</span></div>`)
      .join("");
    summaryBody.innerHTML =
      rows +
      `<div class="summary-total">Total: ${data.totalPatients} pasien, ${data.totalFiles} gambar</div>`;
  }
  if (forceShow) summaryDismissed = false;
  if (!summaryDismissed && options.show !== false) summaryPanel.classList.remove("summary-hidden");
}

function updateSaveButtonState() {
  // Citra diam tampil berdampingan dengan live hanya selama belum disimpan.
  document.getElementById("stillPane").classList.toggle("view-hidden", !(hasCapturedImage && !currentCaptureSaved));
  const hasPatient = !!patientNameInput.value.trim();
  btnSave.disabled = !(hasCapturedImage && selectedFolder && hasPatient);
  prereqCamera.classList.toggle("prereq-ok", isCameraConnected);
  document.getElementById("prereqPatient").parentElement.classList.toggle("prereq-ok", hasPatient);
  document.getElementById("prereqFolder").parentElement.classList.toggle("prereq-ok", !!selectedFolder);
  const missing = [];
  if (!hasCapturedImage) missing.push("ambil citra");
  if (!hasPatient) missing.push("isi inisial pasien");
  if (!selectedFolder) missing.push("pilih lokasi simpan");
  saveHint.textContent = missing.length ? "Sebelum simpan: " + missing.join(", ") + "." : "";
}

// mode "otomatis" hanya dari autoCaptureAndSave; klik tombol/Enter selalu manual.
async function doSave(mode) {
  const currentId = patientNameInput.value.trim();

  // Kalau ID pasien beda dari yang terakhir disimpan di sesi ini, konfirmasi
  // dulu -- biar nggak salah nyimpen ke pasien yang salah tanpa sadar.
  if (lastSavedId && currentId !== lastSavedId) {
    const lanjut = await showConfirmModal(
      `ID pasien berubah dari "${lastSavedId}" ke "${currentId}".\n\n` +
      `Lanjutkan simpan untuk "${currentId}"?`
    );
    if (!lanjut) return;
  }

  // Kalau capture yang sama (belum capture ulang) sudah pernah disimpan,
  // konfirmasi dulu -- biar nggak numpuk file duplikat isinya tanpa sadar.
  if (currentCaptureSaved) {
    const lanjut = await showConfirmModal(
      `Gambar ini sudah disimpan sebelumnya sebagai "${currentCaptureSavedAs}".\n\n` +
      `Simpan lagi sebagai file baru (isi gambarnya tetap sama)?`
    );
    if (!lanjut) return;
  }

  // Peringatan (bukan pemblokiran): fokus terdeteksi buram relatif terhadap
  // puncak yang teramati. Ambangnya masih heuristik, jadi keputusan tetap di operator.
  if (currentCaptureFocus && currentCaptureFocus.status === "buram") {
    const lanjut = await showConfirmModal(
      `Fokus gambar ini terdeteksi buram (${Math.round(currentCaptureFocus.relLow * 100)}% dari puncak fokus).\n\n` +
      `Tetap simpan?`
    );
    if (!lanjut) return;
  }

  const cameraName = cameraSelect.options[cameraSelect.selectedIndex]
    ? cameraSelect.options[cameraSelect.selectedIndex].text
    : "";

  // Kalau kamera tidak bisa diatur resolusinya langsung (mis. MiiCam),
  // width/height ini dipakai backend buat resize software sebelum disimpan.
  let width = null;
  let height = null;
  if (resolutionSelect.value) {
    const [w, h] = resolutionSelect.value.split("x").map(Number);
    width = w;
    height = h;
  }

  const res = await fetch("/api/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      patientName: currentId,
      folder: selectedFolder,
      mode: mode === "otomatis" ? "otomatis" : "manual",
      cameraName,
      width,
      height,
    }),
  });
  const data = await res.json();
  if (!data.ok) {
    // Citra tetap tampil dengan status "Belum Tersimpan"; tawarkan pemulihan sesuai penyebab.
    const folderProblem = ["folder", "permission", "disk_full"].includes(data.code);
    if (!data.offline) {
      showError(
        data.message || "Gagal menyimpan.",
        folderProblem
          ? { label: "Pilih lokasi lain", run: doSelectFolder }
          : { label: "Coba simpan lagi", run: doSave },
        "save"
      );
    }
    return;
  }
  hideError("save");
  captureBadge.textContent = "Tersimpan";
  captureBadge.className = "badge badge-saved";
  captureFilename.textContent = data.filename;
  captureCount.textContent = data.count;
  const savedRes = data.width && data.height ? `, ${data.width}x${data.height}` : "";
  showToast("Tersimpan: " + data.filename + " (iterasi " + data.count + savedRes + ")");
  lastSavedId = currentId;
  currentCaptureSaved = true;
  currentCaptureSavedAs = data.filename;
  updateSaveButtonState(); // live kembali penuh
  lastSavedFullPath = data.path;
  btnSendToSegmentation.disabled = false;
  if (lastCapturedImage) addToGallery(data.filename, lastCapturedImage);
  document.getElementById("sessionCount").textContent = galleryEntries.length;
  loadFolderSummary({ forceShow: false });
  refreshSystemStatus();
}


// -----------------------------------------------------------------------
// Shortcut keyboard buat tab Capture: Spasi = Capture, Enter = Save
// -----------------------------------------------------------------------
window.addEventListener("keydown", (e) => {
  if (captureView.classList.contains("view-hidden") || isOverlayOpen()) return;
  const active = document.activeElement;
  const tag = active ? active.tagName : "";
  const isPatientNameField = active === patientNameInput;

  if (e.key === " " || e.code === "Space") {
    // Jangan sikat spasi kalau lagi ngetik (mis. inisial pasien 2 kata)
    if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
    e.preventDefault();
    if (!btnCapture.disabled) doCapture();
    return;
  }
  if (e.key === "Enter") {
    // Enter aman dipakai walau fokus di field inisial pasien (input teks
    // biasa tanpa <form>, jadi Enter nggak ada default action)
    if ((tag === "SELECT" || tag === "TEXTAREA") && !isPatientNameField) return;
    e.preventDefault();
    if (!btnSave.disabled) doSave();
  }
});

// Peringatan kalau tab ditutup/direload padahal ada hasil capture yang
// belum disimpan -- ini SATU-SATUNYA dialog yang tetap pakai bawaan
// browser (bukan modal custom kayak yang lain), karena beforeunload memang
// tidak bisa dikustomisasi tampilannya di semua browser modern (dibatasi
// spec, buat cegah abuse popup pas nutup tab).
window.addEventListener("beforeunload", (e) => {
  if (hasCapturedImage && !currentCaptureSaved) {
    e.preventDefault();
    e.returnValue = "";
  }
});
