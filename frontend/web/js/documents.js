// File: frontend/web/js/myfiles.js

// Định nghĩa địa chỉ API Backend (từ app.py)
const API_URL = "http://127.0.0.1:5000";

// Chạy code khi trang đã tải xong
document.addEventListener("DOMContentLoaded", () => {
    
    // 1. KIỂM TRA XÁC THỰC
    const token = localStorage.getItem("jwtToken");
    // Nếu có token thì setup header (ẩn nút đăng nhập), nếu không có token vẫn cho phép xem danh sách
    if (token) {
        setupHeader(token);
    }

    // 2. TẢI DỮ LIỆU (nếu không có token, backend sẽ trả về tài liệu public)
    loadUserFiles(token);

    // 3. GẮN SỰ KIỆN CHO MODAL
    addModalListeners(token);
});

/**
 * Cập nhật Header: Ẩn nút Login/Register, hiện Avatar
 */
function setupHeader(token) {
    // Đoạn code này tương tự login.html, đảm bảo header đồng bộ
    // (Bạn có thể tách đoạn này ra file main.js chung sau)
    const loginBtn = document.getElementById("loginBtn");
    const registerBtn = document.getElementById("registerBtn");
    const avatar = document.getElementById("userAvatar");

    if (token) {
        loginBtn.classList.add("hidden");
        registerBtn.classList.add("hidden");
        avatar.classList.remove("hidden");

        avatar.addEventListener("click", () => {
            if (confirm("Bạn có muốn đăng xuất không?")) {
                localStorage.removeItem("jwtToken");
                localStorage.removeItem("userName");
                window.location.href = "login.html";
            }
        });
    }
}

/**
 * Gọi API GET /api/documents?user=true để lấy file của user
 */
async function loadUserFiles(token) {
    const container = document.getElementById("file-list-container");
    const loadingText = document.getElementById("loading-text");

    try {
        // Nếu có token, yêu cầu tài liệu của user (user=true) để hiển thị cả tài liệu của họ và public
        // Nếu không có token, gọi endpoint chung để nhận các tài liệu public
        const url = token ? `${API_URL}/api/documents?user=true` : `${API_URL}/api/documents`;
        const headers = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const response = await fetch(url, { method: 'GET', headers });

        if (response.status === 401) {
            // Nếu token hết hạn hoặc không hợp lệ, xóa token và thử lại để lấy public docs
            if (token) {
                localStorage.removeItem('jwtToken');
                // Tải lại danh sách không cần token
                return loadUserFiles(null);
            }
        }

        const data = await response.json();

        if (response.ok) {
            loadingText.classList.add("hidden"); // Ẩn "Đang tải..."
            // Pass token forward so event handlers can authenticate (token may be null)
            renderFiles(data.documents, token);
        } else {
            loadingText.textContent = `Lỗi: ${data.message}`;
        }
    } catch (error) {
        console.error("Lỗi kết nối:", error);
        loadingText.textContent = "Lỗi kết nối máy chủ. Vui lòng thử lại.";
    }
}

/**
 * Hiển thị danh sách file ra giao diện
 */
function renderFiles(files, token) {
    const container = document.getElementById("file-list-container");
    container.innerHTML = ""; // Xóa sạch container

    if (!files || files.length === 0) {
        container.innerHTML = "<p>Bạn chưa tải lên tài liệu nào. Hãy thử tải lên một file!</p>";
        return;
    }

    files.forEach(file => {
        const fileCard = document.createElement("div");
        fileCard.className = "doc-card"; // Tận dụng style có sẵn từ style.css

        // Chuyển mảng tags thành chuỗi (guard nếu tags undefined)
        const tagsString = (file.tags || []).join(', ');

        // Nội dung hiển thị (an toàn)
        const title = document.createElement('h3');
        title.textContent = file.filename || '';

        const desc = document.createElement('p');
        desc.className = 'desc';
        desc.innerHTML = file.description ? escapeHTML(file.description) : '<i>Chưa có mô tả</i>';

        const infoRow1 = document.createElement('div');
        infoRow1.className = 'info-row';
        infoRow1.innerHTML = `<strong>Trạng thái:</strong> <span class="status ${file.visibility}">${file.visibility === 'public' ? 'Công khai' : 'Riêng tư'}</span>`;

        const infoRow2 = document.createElement('div');
        infoRow2.className = 'info-row';
        infoRow2.innerHTML = `<strong>Tags:</strong> <span>${tagsString || '<i>Không có thẻ</i>'}</span>`;

        const actions = document.createElement('div');
        actions.className = 'doc-card-actions';

        // Only show edit/delete actions if user is authenticated (token present)
        if (token) {
            // Create Edit button and set dataset safely
            const editBtn = document.createElement('button');
            editBtn.className = 'btn-action btn-edit';
            editBtn.type = 'button';
            editBtn.textContent = '✏️ Sửa';
            editBtn.dataset.id = file.id;
            editBtn.dataset.filename = file.filename || '';
            editBtn.dataset.description = file.description || '';
            editBtn.dataset.visibility = file.visibility || '';
            editBtn.dataset.tags = tagsString;

            // Create Delete button
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn-action btn-delete';
            deleteBtn.type = 'button';
            deleteBtn.textContent = '🗑️ Xóa';
            deleteBtn.dataset.id = file.id;

            actions.appendChild(editBtn);
            actions.appendChild(deleteBtn);
        }

        // Append all pieces to card
        fileCard.appendChild(title);
        fileCard.appendChild(desc);
        fileCard.appendChild(infoRow1);
        fileCard.appendChild(infoRow2);
        fileCard.appendChild(actions);

        container.appendChild(fileCard);
    });

    // Sau khi render, gắn một lần listener (delegation) cho container
    addCardButtonListeners(token);
}

/**
 * Gắn sự kiện cho các nút Sửa/Xóa trên mỗi thẻ
 */
function addCardButtonListeners(token) {
    const container = document.getElementById("file-list-container");

    // Use event delegation: one listener for edit/delete actions
    // Remove existing delegated listener if present (idempotent attach)
    if (container._hasDelegatedListener) return;

    container.addEventListener('click', async (e) => {
        const editBtn = e.target.closest('.btn-edit');
        if (editBtn) {
            showEditModal(editBtn.dataset);
            return;
        }

        const deleteBtn = e.target.closest('.btn-delete');
        if (deleteBtn) {
            const fileId = deleteBtn.dataset.id;
            if (!fileId) return;
            if (confirm("Bạn có chắc chắn muốn xóa file này không? Hành động này không thể hoàn tác.")) {
                try {
                    const headers = {};
                    if (token) headers['Authorization'] = `Bearer ${token}`;
                    const response = await fetch(`${API_URL}/api/documents/${fileId}`, {
                        method: "DELETE",
                        headers
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        alert("Xóa tài liệu thành công!");
                        loadUserFiles(token); // Tải lại danh sách file
                    } else {
                        alert(`Lỗi: ${data.message}`);
                    }
                } catch (error) {
                    alert("Lỗi kết nối khi xóa file.");
                }
            }
            return;
        }
    });

    container._hasDelegatedListener = true;
}

/**
 * Hiển thị modal và điền thông tin file vào form
 */
function showEditModal(data) {
    // Điền dữ liệu từ file vào form trong modal
    document.getElementById("edit-id").value = data.id || '';
    document.getElementById("edit-filename").value = data.filename || '';
    document.getElementById("edit-description").value = data.description || '';
    document.getElementById("edit-visibility").value = data.visibility || 'private';
    document.getElementById("edit-tags").value = data.tags || '';

    // Hiển thị modal và cập nhật thuộc tính ARIA
    const overlay = document.getElementById("edit-modal-overlay");
    overlay.classList.remove("hidden");
    overlay.setAttribute('aria-hidden', 'false');

    // Focus vào textarea mô tả để người dùng có thể nhập ngay
    const desc = document.getElementById('edit-description');
    if (desc && typeof desc.focus === 'function') desc.focus();
}

// Hàm ẩn modal (đặt global để có thể dùng từ nhiều nơi)
function hideModal() {
    const overlay = document.getElementById("edit-modal-overlay");
    if (!overlay) return;
    overlay.classList.add("hidden");
    overlay.setAttribute('aria-hidden', 'true');
    // Blur active element to avoid keeping focus on removed controls
    try { if (document.activeElement && document.activeElement.blur) document.activeElement.blur(); } catch (e) {}
}

/**
 * Gắn sự kiện cho các nút trong Modal (Lưu, Hủy, Đóng)
 */
function addModalListeners(token) {
    const modalOverlay = document.getElementById("edit-modal-overlay");
    const closeModalBtn = document.getElementById("modal-close-btn");
    const cancelModalBtn = document.getElementById("modal-cancel-btn");
    const saveModalBtn = document.getElementById("modal-save-btn");

    // Gắn sự kiện sử dụng global hideModal
    closeModalBtn.addEventListener("click", hideModal);
    cancelModalBtn.addEventListener("click", hideModal);

    // Xử lý khi nhấn LƯU THAY ĐỔI
    saveModalBtn.addEventListener("click", async () => {
        // Lấy dữ liệu từ form
        const fileId = document.getElementById("edit-id").value;
        const description = document.getElementById("edit-description").value;
        const visibility = document.getElementById("edit-visibility").value;
        const tagsInput = document.getElementById("edit-tags").value;
        
        // Chuyển chuỗi tags thành mảng
        const tagsArray = tagsInput.split(',')
                                   .map(tag => tag.trim())
                                   .filter(tag => tag.length > 0);

        // Chuẩn bị dữ liệu gửi lên API (theo app.py)
        const updateData = {
            description: description,
            visibility: visibility,
            tags: tagsArray
        };

        try {
            const headers = { "Content-Type": "application/json" };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const response = await fetch(`${API_URL}/api/documents/${fileId}`, {
                method: "PUT",
                headers,
                body: JSON.stringify(updateData)
            });

            const data = await response.json();
            if (response.ok) {
                alert("Cập nhật thành công!");
                hideModal();
                loadUserFiles(token); // Tải lại danh sách file để thấy thay đổi
            } else {
                alert(`Lỗi: ${data.message}`);
            }
        } catch (error) {
            alert("Lỗi kết nối khi cập nhật.");
        }
    });
}

/**
 * Hàm bảo mật nhỏ: Chống XSS (Cross-site scripting)
 * Bằng cách thay thế ký tự < > để trình duyệt không hiểu là HTML
 */
function escapeHTML(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/</g, "&lt;").replace(/>/g, "&gt;");
}