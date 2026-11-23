// Layar Penilaian citra (F14): dokter menilai layak/tidak tiap citra capture,
// buta terhadap nama file dan skor otomatis. Lihat rating.py.
const ratingView = document.getElementById("ratingView");
const ratingRater = document.getElementById("ratingRater");
const ratingFolderPath = document.getElementById("ratingFolderPath");
const ratingImageBody = document.getElementById("ratingImageBody");
const ratingReasons = document.getElementById("ratingReasons");
const ratingNote = document.getElementById("ratingNote");
const btnRateOk = document.getElementById("btnRateOk");
const btnRateBad = document.getElementById("btnRateBad");
const btnRateNext = document.getElementById("btnRateNext");
const btnRatePrev = document.getElementById("btnRatePrev");

let ratingFolder = null;
let ratingItem = null; // {id, position, ...} citra yang sedang dinilai
let ratingVerdict = null; // "layak" | "tidak"
let ratingChosen = new Set();
const ratingHistory = []; // ID yang sudah dinilai di sesi ini, untuk Sebelumnya

function ratingCanSubmit() {
  return ratingItem && (ratingVerdict === "layak" || (ratingVerdict === "tidak" && ratingChosen.size > 0));
}

function renderRatingForm() {
  btnRateOk.setAttribute("aria-pressed", ratingVerdict === "layak");
  btnRateBad.setAttribute("aria-pressed", ratingVerdict === "tidak");
  ratingReasons.classList.toggle("view-hidden", ratingVerdict !== "tidak");
  ratingReasons.querySelectorAll("[data-reason]").forEach((b) =>
    b.setAttribute("aria-pressed", ratingChosen.has(b.dataset.reason))
  );
  btnRateNext.disabled = !ratingCanSubmit();
  btnRatePrev.disabled = ratingHistory.length === 0;
  document.getElementById("ratingHint").textContent =
    ratingVerdict === "tidak" && ratingChosen.size === 0 ? "Pilih minimal satu alasan." : "";
}

function setRatingProgress(done, total) {
  document.getElementById("ratingProgress").textContent = total ? `${done} dari ${total} citra dinilai` : "";
  document.getElementById("ratingBarFill").style.width = total ? `${(done / total) * 100}%` : "0";
}

async function loadRatingItem(id = null) {
  if (!ratingFolder || !ratingRater.value.trim()) {
    ratingImageBody.innerHTML = '<span class="placeholder-text">Isi nama penilai dan pilih folder citra untuk mulai.</span>';
    return;
  }
  const res = await fetch("/api/rating/next", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder: ratingFolder, rater: ratingRater.value.trim(), id }),
  });
  const data = await res.json();
  if (!data.ok) {
    if (!data.offline) showError(data.message || "Gagal memuat citra.");
    return;
  }
  setRatingProgress(data.done, data.total);
  if (data.finished) {
    ratingItem = null;
    document.getElementById("ratingId").textContent = "-";
    ratingImageBody.innerHTML = `<span class="placeholder-text">Semua ${data.total} citra di folder ini sudah dinilai. Terima kasih.<br />Hasil: penilaian_citra.csv di folder citra.</span>`;
    ratingVerdict = null;
    ratingChosen = new Set();
    renderRatingForm();
    return;
  }
  ratingItem = data;
  if (!ratingReasons.querySelector("[data-reason]")) {
    ratingReasons.insertAdjacentHTML(
      "beforeend",
      data.reasons
        .map((r, i) => `<button type="button" class="btn reason-btn" data-reason="${r}" aria-pressed="false">${r} <kbd>${i + 1}</kbd></button>`)
        .join("")
    );
  }
  document.getElementById("ratingId").textContent = data.id;
  ratingImageBody.innerHTML = `<img src="data:image/png;base64,${data.image}" alt="Citra ${data.id}" />`;
  ratingImageBody.querySelector("img").addEventListener("click", (e) => e.target.classList.toggle("image-preview-zoomed"));
  ratingVerdict = data.previous ? data.previous.verdict : null;
  ratingChosen = new Set(data.previous ? data.previous.reasons : []);
  ratingNote.value = data.previous ? data.previous.note : "";
  renderRatingForm();
}

async function submitRating() {
  if (!ratingCanSubmit()) return;
  const res = await fetch("/api/rating/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      folder: ratingFolder,
      rater: ratingRater.value.trim(),
      id: ratingItem.id,
      verdict: ratingVerdict,
      reasons: [...ratingChosen],
      note: ratingNote.value,
    }),
  });
  const data = await res.json();
  if (!data.ok) {
    if (!data.offline) showError(data.message || "Gagal menyimpan penilaian.", { label: "Coba simpan lagi", run: submitRating });
    return;
  }
  ratingHistory.push(ratingItem.id);
  await loadRatingItem();
}

async function selectRatingFolder() {
  const res = await fetch("/api/select-folder", { method: "POST" });
  const data = await res.json();
  if (!data.ok) return;
  ratingFolder = data.path;
  ratingFolderPath.textContent = data.path;
  ratingFolderPath.title = data.path;
  ratingHistory.length = 0;
  loadRatingItem();
}

function setRatingVerdict(v) {
  ratingVerdict = v;
  if (v === "layak") ratingChosen = new Set();
  renderRatingForm();
}

function toggleRatingReason(reason) {
  if (ratingVerdict !== "tidak") ratingVerdict = "tidak";
  if (ratingChosen.has(reason)) ratingChosen.delete(reason);
  else ratingChosen.add(reason);
  renderRatingForm();
}

window.addEventListener("keydown", (e) => {
  if (ratingView.classList.contains("view-hidden") || isOverlayOpen() || !ratingItem) return;
  const tag = document.activeElement ? document.activeElement.tagName : "";
  if (tag === "INPUT" || tag === "TEXTAREA") return;
  const key = e.key.toLowerCase();
  if (key === "l") setRatingVerdict("layak");
  else if (key === "t") setRatingVerdict("tidak");
  else if (key >= "1" && key <= "9") {
    const btn = ratingReasons.querySelectorAll("[data-reason]")[parseInt(key, 10) - 1];
    if (btn) toggleRatingReason(btn.dataset.reason);
  } else if (e.key === "Enter") {
    e.preventDefault();
    submitRating();
  }
});
