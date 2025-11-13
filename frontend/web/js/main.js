// ======================
// Script chung: menu, sidebar, navigation
// ======================
window.API_URL = "http://127.0.0.1:5000";
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
 
window.addEventListener("DOMContentLoaded", () => { 
    setupGlobalUI();
    loadHomepageFeed();
    loadPublicDocuments();
    const searchBtn = document.getElementById("searchBtn");
    if (searchBtn) {
        searchBtn.addEventListener("click", async () => {
            const keyword = document.getElementById("searchInput").value.trim();
            
            // 1. Kiểm tra từ khóa
            if (keyword === "") {
                alert("Vui lòng nhập từ khóa tìm kiếm!");
                return;
            }

            // 2. Lấy token (Vì backend yêu cầu @token_required)
            const token = localStorage.getItem("token");
            if (!token) {
                alert("Bạn cần đăng nhập để sử dụng tính năng tìm kiếm!");
                window.location.href = "login.html";
                return;
            }

            try {
                // 3. SỬA URL: Dùng /api/documents/search thay vì /public
                // 4. SỬA PARAM: Dùng ?q= thay vì ?search=
                const url = `${API_URL}/api/documents/search?q=${encodeURIComponent(keyword)}`;
                
                const response = await fetch(url, { 
                    method: "GET",
                    // 5. THÊM HEADERS: Gửi kèm token
                    headers: {
                        "Authorization": "Bearer " + token,
                        "Content-Type": "application/json"
                    }
                });

                // Xử lý lỗi 401 (hết hạn token) hoặc 403
                if (response.status === 401) {
                    alert("Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.");
                    window.location.href = "login.html";
                    return;
                }

                const data = await response.json();
                const container = document.getElementById("public-docs-grid"); // Hoặc vùng hiển thị kết quả bạn muốn
                container.innerHTML = "";

                // Xử lý hiển thị kết quả
                if (!response.ok || !data.documents || data.documents.length === 0) {
                    container.innerHTML = `<p>${data.message || 'Không tìm thấy tài liệu nào phù hợp.'}</p>`;
                    return;
                }

                // Render danh sách tài liệu tìm được
                data.documents.forEach(doc => {
                    const docCard = document.createElement("div");
                    docCard.className = "doc-card";
                    docCard.dataset.id = doc.id;
                    // Xử lý hiển thị tags
                    const tagsString = (doc.tags && doc.tags.length > 0) ? doc.tags.join(', ') : '<i>Không có thẻ</i>';
                    
                    docCard.innerHTML = `
                        <h3>${doc.filename}</h3>
                        <p>${doc.description || '<i>Chưa có mô tả</i>'}</p>
                        <p>Tags: ${tagsString}</p>
                        <p><small>Người đăng: ${doc.owner_name}</small></p>
                        <div class="doc-card-actions">
                            <button class="btn-action btn-favorite ${doc.is_favorited ? 'favorited' : ''}" data-id="${doc.id}">⭐ Bộ nhớ</button>
                        </div>
                    `;
                    container.appendChild(docCard);
                });
                
                // Gán lại sự kiện click cho các card vừa tạo (để xem chi tiết)
                // Lưu ý: Cần gọi lại logic gán event click viewDocument nếu cần thiết ở đây
                
            } catch (err) {
                console.error("Lỗi tìm kiếm:", err);
                alert("Lỗi kết nối server khi tìm kiếm!");
            }
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

async function loadHomepageFeed() {
    const uploadGrid = document.getElementById("recent-upload-grid");
    if (uploadGrid) {
        try {
            const data = await apiRequest("/documents/recent-public", "GET", null, false);
            if (data.documents && data.documents.length > 0) {
                uploadGrid.innerHTML = ""; 
                data.documents.forEach(doc => {
                    const docCard = `
                        <div class="doc-card" onclick="viewDocument(this)" data-id="${doc.id}">
                            <h3>${doc.filename}</h3>
                            <p>Người đăng: ${doc.owner_name || 'Không rõ'}</p>
                            <p>Ngày tải: ${doc.created_at}</p>
                        </div>
                    `;
                    uploadGrid.innerHTML += docCard;
                });
            } else {
                uploadGrid.innerHTML = "<p>Chưa có tài liệu public nào.</p>";
            }
        } catch (error) {
            console.error("Lỗi tải recent uploads:", error);
            uploadGrid.innerHTML = "<p>Không thể tải tài liệu.</p>";
        }
    }
 
    const viewGrid = document.getElementById("recent-view-grid");
    if (viewGrid) { 
        if (!isLoggedIn()) {  
             viewGrid.innerHTML = '<p><a href="login.html">Đăng nhập</a> để xem lịch sử của bạn.</p>';
        } else { 
            try { 
                const data = await getRecentlyViewed();  
                
                if (data.documents && data.documents.length > 0) {
                    viewGrid.innerHTML = "";  
                    
                    data.documents.forEach(doc => {
                        const docCard = `
                            <div class="doc-card" onclick="viewDocument(this)" data-id="${doc.id}">
                                <h3>${doc.filename}</h3>
                                <p>Người đăng: ${doc.owner_name || 'Không rõ'}</p>
                                <p style="font-weight: bold;">Vừa xem gần đây</p> 
                            </div>
                        `;
                        viewGrid.innerHTML += docCard;
                    });
                } else {
                    viewGrid.innerHTML = "<p>Bạn chưa xem tài liệu nào.</p>";
                }
            } catch (error) {
                console.error("Lỗi tải recent views:", error);
                viewGrid.innerHTML = "<p>Không thể tải lịch sử xem.</p>";
            }
        }
    }
}
async function loadPublicDocuments() {
    const container = document.getElementById("public-docs-grid");
    container.innerHTML = "<p>Đang tải...</p>";

    try {
        const response = await fetch(`${API_URL}/api/documents/public`, { method: 'GET' });
        const data = await response.json();

        if (response.ok) {
            container.innerHTML = "";
            if (!data.documents || data.documents.length === 0) {
                container.innerHTML = "<p>Hiện chưa có tài liệu public nào.</p>";
                return;
            }

            data.documents.forEach(doc => {
                const docCard = document.createElement("div");
                docCard.className = "doc-card";
                docCard.dataset.id = doc.id;

                const tagsString = (doc.tags || []).join(', ');

                docCard.innerHTML = `
                    <h3>${doc.filename}</h3>
                    <p>${doc.description || '<i>Chưa có mô tả</i>'}</p>
                    <p>Tags: ${tagsString || '<i>Không có thẻ</i>'}</p>
                    <div class="doc-card-actions">
                        <button class="btn-action btn-favorite ${doc.is_favorited ? 'favorited' : ''}" data-id="${doc.id}">⭐ Bộ nhớ</button>
                    </div>
                `;

                container.appendChild(docCard);
            });
 
            container.addEventListener('click', async (e) => {
                const favBtn = e.target.closest('.btn-favorite');
                if (favBtn) {
                    e.stopPropagation(); 
                    const docId = favBtn.dataset.id;
                    const token = localStorage.getItem('token');
                    if (!token) {
                        alert("Vui lòng đăng nhập để thêm vào Bộ nhớ của tôi!");
                        return;
                    }
                    try {
                        const data = await toggleFavorite(docId);
                        if (data.isFavorited) {
                            favBtn.classList.add('favorited');
                        } else {
                            favBtn.classList.remove('favorited');
                        }
                    } catch (err) {
                        alert("Lỗi: " + err.message);
                    }
                    return;
                }

                const card = e.target.closest('.doc-card');
                if (card && typeof viewDocument === 'function') {
                    viewDocument(card);
                }
            });

        } else {
            container.innerHTML = `<p>Lỗi: ${data.message}</p>`;
        }
    } catch (err) {
        console.error(err);
        container.innerHTML = "<p>Lỗi kết nối máy chủ.</p>";
    }
}

