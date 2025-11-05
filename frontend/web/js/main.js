// ======================
// Script chung: menu, sidebar, navigation
// ======================

// Hàm này phải được gọi bởi TẤT CẢ các trang (trừ login/register)
// Nó dựa vào file api.js (phải được tải trước)
function setupGlobalUI() {
    // Đảm bảo hàm isLoggedIn từ api.js đã tồn tại
    if (typeof isLoggedIn !== 'function') {
        console.error("Lỗi: api.js chưa được tải. Không thể setup UI.");
        return;
    }

    const token = isLoggedIn(); // Dùng hàm từ api.js
    
    // Lấy tất cả các nút
    const loginBtn = document.getElementById("loginBtn");
    const registerBtn = document.getElementById("registerBtn");
    const logoutBtn = document.getElementById("logoutBtn"); // Nút đăng xuất mới

    if (token) {
        // === ĐÃ ĐĂNG NHẬP ===
        if (loginBtn) loginBtn.classList.add("hidden");
        if (registerBtn) registerBtn.classList.add("hidden");
        
        // Hiện nút Đăng xuất
        if (logoutBtn) {
            logoutBtn.classList.remove("hidden");
            
            // Gán sự kiện click để gọi hàm logout() từ api.js
            logoutBtn.addEventListener("click", () => {
                if (confirm("Bạn có muốn đăng xuất không?")) {
                    // Đảm bảo hàm logout từ api.js đã tồn tại
                    if (typeof logout === 'function') {
                        logout(); 
                    } else {
                        console.error("Lỗi: Hàm logout() không tìm thấy trong api.js");
                    }
                }
            });
        }

    } else {
        // === CHƯA ĐĂNG NHẬP ===
        if (loginBtn) loginBtn.classList.remove("hidden");
        if (registerBtn) registerBtn.classList.remove("hidden");
        
        // Ẩn nút Đăng xuất
        if (logoutBtn) logoutBtn.classList.add("hidden");
    }
}

// Chạy hàm setup khi trang tải xong
window.addEventListener("DOMContentLoaded", () => {
    // 1. Chạy hàm setup nút (Đăng nhập/Đăng ký/Đăng xuất)
    setupGlobalUI();

    // 2. Xử lý tìm kiếm (code cũ của bạn)
    const searchBtn = document.getElementById("searchBtn");
    if (searchBtn) {
        searchBtn.addEventListener("click", () => {
            const keyword = document.getElementById("searchInput").value.trim();
            if (keyword === "") {
                alert("Vui lòng nhập từ khóa tìm kiếm!");
                return;
            }
            alert(`Đang tìm kiếm tài liệu liên quan đến: ${keyword}`);
        });
    }
});


// ======================
// 📄 Xem chi tiết & Xem trước tài liệu
// (Giữ nguyên code của bạn)
// ====================== 

function viewDocument(el) {
    const docId = el.dataset.id;
    const token = localStorage.getItem("token"); // Đảm bảo dùng 'token' (đã sửa)
    if (!token) {
        alert("Vui lòng đăng nhập trước khi xem tài liệu!");
        window.location.href = "login.html";
        return;
    }

    // Kiểm tra xem apiRequest (từ api.js) có tồn tại không
    if (typeof apiRequest !== 'function') {
        alert("Lỗi: api.js chưa tải xong. Không thể xem tài liệu.");
        return;
    }
    
    // SỬA: Dùng apiRequest thay vì fetch để tự động xử lý lỗi 401
    apiRequest(`/documents/${docId}`, "GET")
        .then(data => {
            if (data.message) { // apiRequest có thể vẫn trả về data.message nếu logic backend xử lý riêng
                alert("⚠️ " + data.message);
            } else {
                // Xây đường dẫn file thật để nhúng xem
                // Chú ý: Cần đảm bảo backend (5000) có thể phục vụ file tĩnh từ /storage/uploads
                // Đây là một rủi ro bảo mật nếu không cấu hình đúng.
                
                // Giả sử file_path trả về là "upload_id/filename.pdf"
                // và app.py có 1 route tĩnh phục vụ "storage/uploads"
                // Tạm thời, chúng ta cần 1 route tĩnh an toàn.
                
                // Cách đơn giản nhất (NHƯNG KÉM AN TOÀN):
                // Cần cấu hình Flask để phục vụ file từ /storage/uploads
                // Dựa trên app.py, file_path lưu là "relative_path"
                // Ví dụ: "1678886400_Test.pdf" (nếu lưu phẳng)
                // hoặc "123456_id/Test.pdf" (nếu lưu theo upload_id)
                
                // Giả sử app.py lưu "123456_id/Test.pdf" và STORAGE_DIR là "../storage/uploads"
                // Đường dẫn trong DB (doc.file_path) là "123456_id/Test.pdf"
                
                // Vấn đề: Cổng 5000 (Flask) không tự động phục vụ file tĩnh từ /storage/uploads
                // Route /download của bạn yêu cầu token.
                
                // -> Chúng ta nên dùng route /download an toàn
                downloadAndPreview(docId, data.filename);
            }
        })
        .catch(err => {
            console.error("Lỗi khi xem tài liệu:", err);
            // apiRequest đã tự showError(err.message)
        });
}

/**
 * Hàm mới: Tải file (dưới dạng blob) và hiển thị trong Iframe
 * An toàn hơn là lộ link trực tiếp
 */
async function downloadAndPreview(docId, filename) {
    try {
        const token = localStorage.getItem("token");
        const response = await fetch(`${API_BASE}/documents/${docId}/download`, {
            headers: { "Authorization": "Bearer " + token }
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.message || `Lỗi tải file (${response.status})`);
        }

        const blob = await response.blob();
        const fileUrl = URL.createObjectURL(blob);
        
        // Xác định xem file có phải PDF hay không
        const isPDF = filename.toLowerCase().endsWith(".pdf");

        // Nếu là PDF, nhúng trực tiếp.
        // Nếu không phải, Google Viewer KHÔNG THỂ xem blob URL.
        // Google Viewer yêu cầu URL công khai.
        
        let previewUrl;
        if (isPDF) {
            previewUrl = fileUrl;
        } else {
            // Đối với DOCX, PPTX... chúng ta không thể dùng Google Viewer với blob.
            // Giải pháp: Hiển thị thông báo "Không hỗ trợ xem trước" hoặc "Đang tải về"
            alert("Không hỗ trợ xem trước cho định dạng file này. Tệp sẽ được tải về.");
            
            // Tạo link ẩn để tải về
            const link = document.createElement('a');
            link.href = fileUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            return;
        }
        
        // Tạo popup (code cũ của bạn)
        const popup = document.createElement("div");
        popup.className = "modal-overlay";
        popup.innerHTML = `
          <div class="modal-box" style="max-width: 90%; width: 900px; height: 90vh; display:flex; flex-direction:column;">
            <div class="modal-header">
              <h3>${filename}</h3>
              <button class="modal-close-btn" onclick="this.closest('.modal-overlay').remove()">×</button>
            </div>
            <div class="modal-body" style="flex:1; overflow:hidden;">
              <iframe src="${previewUrl}" 
                      style="width:100%; height:100%; border:none;"
                      title="Xem tài liệu"></iframe>
            </div>
          </div>`;
        document.body.appendChild(popup);

    } catch (err) {
        console.error("Lỗi khi tải/xem trước tài liệu:", err);
        alert(`Không thể tải tài liệu: ${err.message}`);
    }
}
