// =============================
// 📂 FILE UPLOAD MODULE (DEMO VERSION)
// =============================

// --- DOM Elements ---
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const browseFile = document.getElementById("browseFile");

const startBtn = document.getElementById("startBtn");
const pauseBtn = document.getElementById("pauseBtn");
const resumeBtn = document.getElementById("resumeBtn");
const stopBtn = document.getElementById("stopBtn");

const progressBar = document.getElementById("progress");
const statusText = document.getElementById("statusText");

// --- State Variables ---
let selectedFile = null;
let uploadProgress = 0;
let uploadInterval = null;
let isPaused = false;
let isUploading = false;

// =============================
// 🖱️ Drag & Drop File Logic
// =============================
dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  handleFileSelection(file);
});

// =============================
// 📁 File Selection via Input
// =============================
browseFile.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  handleFileSelection(file);
});

function handleFileSelection(file) {
  if (!file) return;
  selectedFile = file;
  dropZone.innerHTML = `<p>📄 <strong>${file.name}</strong> (${(file.size / 1024 / 1024).toFixed(2)} MB)</p>`;
  statusText.textContent = "Tệp đã sẵn sàng để tải lên.";
  resetProgress();
}

// =============================
// ▶️ Start Upload (Demo Simulation)
// =============================
startBtn.addEventListener("click", () => {
  if (!selectedFile) {
    alert("⚠️ Vui lòng chọn tệp để tải lên!");
    return;
  }
  if (isUploading) return;

  isUploading = true;
  uploadProgress = 0;
  updateButtons("start");
  statusText.textContent = "Đang tải lên...";

  // Giả lập tiến trình upload
  uploadInterval = setInterval(() => {
    if (isPaused) return;

    uploadProgress += 2; // tăng 2% mỗi lần
    updateProgress(uploadProgress);

    if (uploadProgress >= 100) {
      completeUpload();
    }
  }, 150);
});

// =============================
// ⏸ Pause / ▶️ Resume / ⛔ Stop
// =============================
pauseBtn.addEventListener("click", () => {
  if (!isUploading) return;
  isPaused = true;
  updateButtons("pause");
  statusText.textContent = "⏸ Upload đã tạm dừng.";
});

resumeBtn.addEventListener("click", () => {
  if (!isUploading) return;
  isPaused = false;
  updateButtons("resume");
  statusText.textContent = "▶️ Tiếp tục upload...";
});

stopBtn.addEventListener("click", stopUpload);

function stopUpload() {
  clearInterval(uploadInterval);
  isUploading = false;
  isPaused = false;
  resetProgress();
  updateButtons("stop");
  statusText.textContent = "⛔ Upload đã dừng.";
}

// =============================
// 📊 UI Helper Functions
// =============================
function updateProgress(percent) {
  const safePercent = Math.min(percent, 100);
  progressBar.style.width = `${safePercent}%`;
  statusText.textContent = `Đang tải lên... ${safePercent.toFixed(1)}%`;
}

function completeUpload() {
  clearInterval(uploadInterval);
  uploadProgress = 100;
  isUploading = false;
  updateProgress(100);
  updateButtons("complete");
  statusText.textContent = "✅ Upload hoàn tất!";
}

function resetProgress() {
  uploadProgress = 0;
  progressBar.style.width = "0%";
}

function updateButtons(state) {
  switch (state) {
    case "start":
      startBtn.disabled = true;
      pauseBtn.disabled = false;
      resumeBtn.disabled = true;
      stopBtn.disabled = false;
      break;
    case "pause":
      pauseBtn.disabled = true;
      resumeBtn.disabled = false;
      break;
    case "resume":
      pauseBtn.disabled = false;
      resumeBtn.disabled = true;
      break;
    case "complete":
    case "stop":
      startBtn.disabled = false;
      pauseBtn.disabled = true;
      resumeBtn.disabled = true;
      stopBtn.disabled = true;
      break;
    default:
      startBtn.disabled = false;
      pauseBtn.disabled = true;
      resumeBtn.disabled = true;
      stopBtn.disabled = true;
  }
}
