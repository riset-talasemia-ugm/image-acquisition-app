// Elemen dan fungsi bersama kedua layar: toast, modal pilihan, pindah layar.
const tabCapture = document.getElementById("tabCapture");
const tabSegmentation = document.getElementById("tabSegmentation");
const captureView = document.getElementById("captureView");
const segmentationView = document.getElementById("segmentationView");

const confirmModal = document.getElementById("confirmModal");
const confirmModalMessage = document.getElementById("confirmModalMessage");
const confirmModalActions = document.getElementById("confirmModalActions");

const errorBar = document.getElementById("errorBar");
const errorText = document.getElementById("errorText");
const errorAction = document.getElementById("errorAction");
let errorKey = null; // jenis galat yang sedang tampil, supaya bisa dihapus otomatis saat pulih

// Galat tetap tampil sampai ditutup, dengan tombol pemulihan opsional
// ({label, run}). `key` dipakai hideError untuk menghapusnya hanya bila galat
// yang tampil masih galat yang sama.
function showError(message, action = null, key = null) {
  errorKey = key;
  errorText.textContent = message;
  errorAction.hidden = !action;
  errorAction.onclick = action
    ? () => {
        hideError();
        action.run();
      }
    : null;
  if (action) errorAction.textContent = action.label;
  errorBar.classList.remove("view-hidden");
}

function hideError(key = null) {
  if (key && key !== errorKey) return;
  errorBar.classList.add("view-hidden");
  errorKey = null;
}
document.getElementById("errorClose").addEventListener("click", () => hideError());

// Semua request lewat fetch ini. Kalau server tidak bisa dihubungi, pemanggil
// menerima respons {ok:false, offline:true} alih-alih exception, jadi jalur
// galat yang sudah ada di tiap pemanggil (termasuk mengaktifkan lagi tombol
// yang dimatikan selama request) tetap jalan, dan pengguna melihat satu pesan
// "Terputus dari aplikasi" yang hilang sendiri begitu server kembali.
const nativeFetch = window.fetch.bind(window);
let appOffline = false;
let offlineProbe = null;
window.fetch = async (...args) => {
  try {
    const res = await nativeFetch(...args);
    if (appOffline) {
      appOffline = false;
      clearInterval(offlineProbe);
      hideError("offline");
      showToast("Tersambung lagi ke aplikasi.");
    }
    return res;
  } catch (e) {
    if (!appOffline) {
      appOffline = true;
      showError(
        "Terputus dari aplikasi: server tidak merespons. Mungkin jendela run.bat tertutup atau perangkat tertidur. " +
          "Jalankan lagi run.bat; citra yang sudah tersimpan aman.",
        null,
        "offline"
      );
      offlineProbe = setInterval(() => fetch("/api/camera/status"), 3000);
    }
    return new Response(
      JSON.stringify({ ok: false, offline: true, message: "Terputus dari aplikasi." }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }
};

function showToast(message) {
  toast.textContent = message;
  toast.classList.remove("toast-hidden");
  setTimeout(() => toast.classList.add("toast-hidden"), 3000);
}

// Pengganti window.confirm()/window.prompt() bawaan browser -- tampilannya
// konsisten dengan desain aplikasi (bukan popup native OS/browser), dan tetap
// modal (nge-block interaksi lain sampai user pilih salah satu tombol).
// `choices` adalah array [{label, value, primary}], resolve dengan `value`
// dari tombol yang diklik. Dipakai buat kasus lebih dari sekadar
// Batal/Lanjutkan, mis. 3 pilihan di konfirmasi Proses Batch.
function showChoiceModal(message, choices) {
  return new Promise((resolve) => {
    confirmModalMessage.textContent = message;
    confirmModalActions.innerHTML = "";

    function cleanup(value) {
      confirmModal.classList.add("modal-hidden");
      confirmModalActions.innerHTML = "";
      resolve(value);
    }

    choices.forEach((choice) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = choice.label;
      btn.className = "btn " + (choice.primary ? "btn-primary" : "btn-outline");
      btn.addEventListener("click", () => cleanup(choice.value));
      confirmModalActions.appendChild(btn);
    });

    confirmModal.classList.remove("modal-hidden");
    // Fokus ke pilihan utama supaya Enter/Spasi langsung memilihnya.
    const primary = confirmModalActions.querySelector(".btn-primary") || confirmModalActions.lastChild;
    if (primary) primary.focus();
  });
}

// Pengganti window.confirm() sederhana (2 pilihan: Batal/Lanjutkan) -- dibuat
// di atas showChoiceModal supaya semua pemanggil lama (doSave, dst) nggak
// perlu diubah.
function showConfirmModal(message) {
  return showChoiceModal(message, [
    { label: "Batal", value: false },
    { label: "Lanjutkan", value: true, primary: true },
  ]);
}

function switchTab(tab) {
  const isCapture = tab === "capture";
  tabCapture.classList.toggle("tab-active", isCapture);
  tabSegmentation.classList.toggle("tab-active", !isCapture);
  captureView.classList.toggle("view-hidden", !isCapture);
  segmentationView.classList.toggle("view-hidden", isCapture);
  tabCapture.setAttribute("aria-current", isCapture ? "step" : "false");
  tabSegmentation.setAttribute("aria-current", isCapture ? "false" : "step");
}

// Dialog <dialog> (Laporan, Pengaturan model) atau modal konfirmasi/preview
// sedang terbuka: shortcut layar di belakangnya tidak boleh ikut bereaksi.
function isOverlayOpen() {
  return (
    !!document.querySelector("dialog[open]") ||
    !confirmModal.classList.contains("modal-hidden")
  );
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("adt-theme", next);
}
