/* ========== CẤU HÌNH ========== */
const API_BASE = "http://localhost:5000/api"; // sửa nếu backend đổi port / domain
const TOKEN_KEY = "token"; // key lưu token trong localStorage
const USER_KEY = "user";   // key lưu thông tin user (nếu backend trả)

/* ========== TIỆN ÍCH HIỂN THỊ LỖI ========== */
function showError(message) {
  console.error("API Error:", message);
  // Nếu có element .msg hiện trên trang thì hiển thị ở đó, nếu không dùng alert
  const msgEl = document.querySelector(".msg");
  if (msgEl) {
    msgEl.textContent = message;
    msgEl.classList.remove("success");
    msgEl.classList.add("error");
  } else {
    alert("❌ " + message);
  }
}

/* ========== HÀM CHUNG GỌI API ========== */
/**
 * apiRequest: wrapper chung cho fetch
 * - endpoint: đường dẫn sau /api (ví dụ "/login")
 * - method: "GET"|"POST"|...
 * - body: object (JSON) hoặc FormData (file)
 * - requireAuth: nếu true thì thêm header Authorization (nếu có token)
 */
async function apiRequest(endpoint, method = "GET", body = null, requireAuth = true) {
  const headers = {};
  const token = localStorage.getItem(TOKEN_KEY);

  // Nếu body không phải FormData thì set Content-Type JSON
  if (body && !(body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (requireAuth && token) headers["Authorization"] = `Bearer ${token}`;

  const options = { method, headers };
  if (body) options.body = body instanceof FormData ? body : JSON.stringify(body);

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, options);

    // Xử lý HTTP 204 No Content
    if (res.status === 204) return null;

    // Thử parse JSON (nếu không phải JSON sẽ trả rỗng)
    const data = await res.json().catch(() => ({}));

    // Nếu 401 Unauthorized -> token sai/hết hạn => logout + redirect
    if (res.status === 401) {
      // Clear token & user
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      showError("Phiên đã hết hạn. Vui lòng đăng nhập lại.");
      // Tự động chuyển hướng tới login (nếu đang không ở trang login)
      if (!location.pathname.endsWith("login.html")) {
        setTimeout(() => (window.location.href = "login.html"), 800);
      }
      throw new Error(data.message || "Unauthorized");
    }

    if (!res.ok) {
      const message = data.message || `Lỗi API (${res.status})`;
      throw new Error(message);
    }

    return data;
  } catch (err) {
    // Nếu lỗi mạng (fetch failed) hoặc lỗi khác
    showError(err.message || "Không thể kết nối tới máy chủ");
    throw err;
  }
}

/* ========== AUTH (Đăng ký/Đăng nhập/Đăng xuất) ========== */

/**
 * register(name, email, password)
 * - Không yêu cầu token
 */
async function register(name, email, password) {
  try {
    const data = await apiRequest("/register", "POST", { name, email, password }, false);
    // backend có thể trả data.message
    return data;
  } catch (err) {
    // apiRequest đã showError
    throw err;
  }
}

/**
 * login(email, password)
 * - Lưu token + user vào localStorage nếu thành công
 */
async function login(email, password) {
  try {
    const data = await apiRequest("/login", "POST", { email, password }, false);
    if (data.token) {
      localStorage.setItem(TOKEN_KEY, data.token);
      if (data.user) localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    }
    return data;
  } catch (err) {
    throw err;
  }
}

function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  // redirect về login
  window.location.href = "login.html";
}

/* ========== DOCUMENT CRUD & METADATA ========== */

/**
 * createDocumentMetadata(filename, file_path, description, visibility, tags)
 * - file_path: đường dẫn file trên server (do backend trả sau upload)
 */
async function createDocumentMetadata(filename, file_path, description, visibility = "private", tags = []) {
  try {
    const payload = { filename, file_path, description, visibility, tags };
    const data = await apiRequest("/documents", "POST", payload);
    return data;
  } catch (err) {
    throw err;
  }
}

/**
 * getDocuments()
 */
async function getDocuments() {
  try {
    const data = await apiRequest("/documents", "GET");
    // backend thường trả { documents: [...] } hoặc list trực tiếp
    return data;
  } catch (err) {
    throw err;
  }
}

/**
 * downloadDocument(doc_id)
 * - mở tab mới với token query param (nếu backend dùng token query)
 * - hoặc tải blob nếu muốn xử lý trong trang
 */
function downloadDocument(doc_id) {
  const token = localStorage.getItem(TOKEN_KEY);
  const url = `${API_BASE}/documents/${doc_id}/download${token ? `?token=${token}` : ""}`;
  window.open(url, "_blank");
}

/**
 * deleteDocument(doc_id)
 */
async function deleteDocument(doc_id) {
  try {
    const data = await apiRequest(`/documents/${doc_id}`, "DELETE");
    return data;
  } catch (err) {
    throw err;
  }
}

/**
 * updateDocumentFile(doc_id, newFile)
 * - newFile: File object (FormData)
 */
async function updateDocumentFile(doc_id, newFile) {
  try {
    const form = new FormData();
    form.append("file", newFile);
    // apiRequest tự động bỏ Content-Type khi body là FormData
    const data = await apiRequest(`/documents/${doc_id}`, "PUT", form);
    return data;
  } catch (err) {
    throw err;
  }
}

/* ========== COMMENTS / RATINGS / REPORT ========== */

async function addComment(doc_id, content) {
  try {
    const data = await apiRequest(`/documents/${doc_id}/comments`, "POST", { content });
    return data;
  } catch (err) {
    throw err;
  }
}

async function getComments(doc_id) {
  try {
    // comments thường public, nên requireAuth = false
    const data = await apiRequest(`/documents/${doc_id}/comments`, "GET", null, false);
    return data.comments || data || [];
  } catch (err) {
    return []; // trên UI xử lý rỗng
  }
}

async function rateDocument(doc_id, stars) {
  try {
    const data = await apiRequest(`/documents/${doc_id}/rate`, "POST", { rating: stars });
    return data;
  } catch (err) {
    throw err;
  }
}

async function reportDocument(doc_id, reason) {
  try {
    const data = await apiRequest(`/documents/${doc_id}/report`, "POST", { reason });
    return data;
  } catch (err) {
    throw err;
  }
}

/* ========== SOCKET UPLOAD TRIGGER ========== */
/* ========== THÙNG RÁC (TRASH) ========== */

async function trashDocument(doc_id) {
    // Dùng POST
    return apiRequest(`/documents/${doc_id}/trash`, "POST");
}

async function restoreDocument(doc_id) {
    return apiRequest(`/documents/${doc_id}/restore`, "POST");
}

async function permanentDeleteDocument(doc_id) {
    // Dùng DELETE
    return apiRequest(`/documents/${doc_id}/permanent`, "DELETE");
}

async function getTrashDocuments() {
    return apiRequest("/documents/trash", "GET");
}

/* ========== YÊU THÍCH (FAVORITES) ========== */

async function toggleFavorite(doc_id) {
    return apiRequest(`/documents/${doc_id}/favorite`, "POST");
}

async function getFavoriteDocuments() {
    return apiRequest("/documents/favorites", "GET");
}

/* ========== NỘI DUNG GẦN ĐÂY (RECENT) ========== */

async function getRecentlyViewed() {
    return apiRequest("/documents/recently-viewed", "GET");
}
async function getSocketUploadURL() {
  try {
    const data = await apiRequest("/upload/trigger", "POST");
    return data.socket_url;
  } catch (err) {
    throw err;
  }
}
 
/* ========== TIỆN ÍCH ========== */

function getCurrentUser() {
  const u = localStorage.getItem(USER_KEY);
  return u ? JSON.parse(u) : null;
}

function isLoggedIn() {
  return !!localStorage.getItem(TOKEN_KEY);
}

/* ========== USER SETTINGS ========== */

async function getMe() { 
    return apiRequest("/me", "GET");
}

async function updateMe(name) { 
    return apiRequest("/me", "PUT", { name });
}

async function changePassword(old_password, new_password) { 
    return apiRequest("/change-password", "POST", { old_password, new_password });
}