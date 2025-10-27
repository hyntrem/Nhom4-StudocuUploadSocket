// Xử lý upload file qua socket, gửi chunk, pause/resume

// ===== Upload UI Logic =====
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const browseFile = document.getElementById("browseFile");

const startBtn = document.getElementById("startBtn");
const pauseBtn = document.getElementById("pauseBtn");
const resumeBtn = document.getElementById("resumeBtn");
const stopBtn = document.getElementById("stopBtn");

const progressBar = document.getElementById("progress");
const statusText = document.getElementById("statusText");

let selectedFile = null;
let uploadProgress = 0;
let isPaused = false;
let uploadInterval = null;

// ====== Drag & Drop ======
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
  selectedFile = e.dataTransfer.files[0];
  dropZone.innerHTML = `<p>📄 ${selectedFile.name} (${(selectedFile.size / 1024 / 1024).toFixed(2)} MB)</p>`;
});

browseFile.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => {
  selectedFile = e.target.files[0];
  dropZone.innerHTML = `<p>📄 ${selectedFile.name} (${(selectedFile.size / 1024 / 1024).toFixed(2)} MB)</p>`;
});

// ====== Upload Control Logic ======
startBtn.addEventListener("click", () => {
  if (!selectedFile) {
    alert("Vui lòng chọn tệp để upload!");
    return;
  }
  uploadProgress = 0;
  startBtn.disabled = true;
  pauseBtn.disabled = false;
  stopBtn.disabled = false;
  statusText.textContent = "Đang tải lên...";
  
  // giả lập upload (demo)
  uploadInterval = setInterval(() => {
    if (!isPaused) {
      uploadProgress += 2;
      progressBar.style.width = uploadProgress + "%";
      if (uploadProgress >= 100) {
        clearInterval(uploadInterval);
        statusText.textContent = "✅ Upload hoàn tất!";
        startBtn.disabled = false;
        pauseBtn.disabled = true;
        resumeBtn.disabled = true;
        stopBtn.disabled = true;
      }
    }
  }, 150);
});

pauseBtn.addEventListener("click", () => {
  isPaused = true;
  pauseBtn.disabled = true;
  resumeBtn.disabled = false;
  statusText.textContent = "⏸ Tạm dừng upload...";
});

resumeBtn.addEventListener("click", () => {
  isPaused = false;
  pauseBtn.disabled = false;
  resumeBtn.disabled = true;
  statusText.textContent = "▶️ Tiếp tục upload...";
});

stopBtn.addEventListener("click", () => {
  clearInterval(uploadInterval);
  uploadProgress = 0;
  progressBar.style.width = "0%";
  statusText.textContent = "⛔ Upload đã dừng!";
  startBtn.disabled = false;
  pauseBtn.disabled = true;
  resumeBtn.disabled = true;
  stopBtn.disabled = true;
});
