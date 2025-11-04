// ======================
// Script chung: menu, sidebar, navigation
// ======================

document.getElementById("searchBtn").addEventListener("click", () => {
  const keyword = document.getElementById("searchInput").value.trim();
  if (keyword === "") {
    alert("Vui lòng nhập từ khóa tìm kiếm!");
    return;
  }
  alert(`Đang tìm kiếm tài liệu liên quan đến: ${keyword}`);
});

window.addEventListener("DOMContentLoaded", () => {
  const token = localStorage.getItem("token");
  const loginBtn = document.getElementById("loginBtn");
  const registerBtn = document.getElementById("registerBtn");
  const avatar = document.getElementById("userAvatar");

  if (token) {
    // Đã đăng nhập
    if (loginBtn) loginBtn.classList.add("hidden");
    if (registerBtn) registerBtn.classList.add("hidden");
    if (avatar) avatar.classList.remove("hidden");

    // Click avatar để đăng xuất
    if (avatar) {
      avatar.addEventListener("click", () => {
        if (confirm("Bạn có muốn đăng xuất không?")) {
          localStorage.removeItem("token");
          window.location.reload();
        }
      });
    }
  } else {
    // Chưa đăng nhập
    if (loginBtn) loginBtn.classList.remove("hidden");
    if (registerBtn) registerBtn.classList.remove("hidden");
    if (avatar) avatar.classList.add("hidden");
  }
});

// ======================
// 📄 Xem chi tiết & Xem trước tài liệu
// ======================
const API_BASE = "http://127.0.0.1:5000/api";

function viewDocument(el) {
  const docId = el.dataset.id;
  const token = localStorage.getItem("token");
  if (!token) {
    alert("Vui lòng đăng nhập trước khi xem tài liệu!");
    window.location.href = "login.html";
    return;
  }

  fetch(`${API_BASE}/documents/${docId}`, {
    headers: { "Authorization": "Bearer " + token }
  })
    .then(res => res.json())
    .then(data => {
      if (data.message) {
        alert("⚠️ " + data.message);
      } else {
        // Xây đường dẫn file thật để nhúng xem
        const filePath = data.file_path?.replace(/^\/?uploads\//, "uploads/");
        const viewUrl = `http://127.0.0.1:5000/${filePath}`;

        // Xác định xem file có phải PDF hay không
        const isPDF = data.filename.toLowerCase().endsWith(".pdf");

        // Nếu không phải PDF, dùng Google Docs Viewer (xem doc, docx, ppt, xls)
        const previewUrl = isPDF
          ? viewUrl
          : `https://docs.google.com/gview?url=${encodeURIComponent(viewUrl)}&embedded=true`;

        const popup = document.createElement("div");
        popup.className = "modal-overlay";
        popup.innerHTML = `
          <div class="modal-box" style="max-width: 90%; width: 900px; height: 90vh; display:flex; flex-direction:column;">
            <div class="modal-header">
              <h3>${data.filename}</h3>
              <button class="modal-close-btn" onclick="this.closest('.modal-overlay').remove()">×</button>
            </div>
            <div class="modal-body" style="flex:1; overflow:hidden;">
              <iframe src="${previewUrl}" 
                      style="width:100%; height:100%; border:none;"
                      title="Xem tài liệu"></iframe>
            </div>
          </div>`;
        document.body.appendChild(popup);
      }
    })
    .catch(err => {
      console.error("Lỗi khi xem tài liệu:", err);
      alert("Không thể tải thông tin tài liệu.");
    });
}
