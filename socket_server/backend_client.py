"""
BackendClient - Thông báo cho Flask API khi upload hoàn tất qua socket.
"""

import os
import threading
import time

try:
    import requests
except ImportError:
    raise ImportError("⚠️ Thiếu thư viện 'requests'. Cài đặt bằng: pip install requests")

# =============================================
# ⚙️ Cấu hình chung
# =============================================
BACKEND_URL = os.environ.get('BACKEND_URL', 'http://127.0.0.1:5000/api/documents')
_TIMEOUT = 5  # Thời gian chờ request (giây)


# =============================================
# 🧩 Hàm tiện ích
# =============================================
def safe_post(url: str, payload: dict, headers: dict):
    """
    Thực hiện POST request an toàn, có xử lý lỗi.
    """
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT)

        if response.status_code == 201:
            print(f"[BackendClient] ✅ Báo cáo hoàn tất: {payload.get('filename')}")
        else:
            print(
                f"[BackendClient] ⚠️ Báo cáo thất bại ({response.status_code}) "
                f"- {response.text[:200]}"
            )

    except requests.exceptions.Timeout:
        print("[BackendClient] ⏱️ Hết thời gian chờ phản hồi từ Backend.")
    except requests.exceptions.ConnectionError:
        print("[BackendClient] 🚫 Không thể kết nối tới Backend API.")
    except Exception as e:
        print(f"[BackendClient] ❌ Lỗi không xác định khi POST: {e}")


# =============================================
# 🚀 Lớp BackendClient
# =============================================
class BackendClient:
    """
    Gửi thông báo cho API Flask sau khi upload hoàn tất.
    Dùng để đồng bộ metadata (tên file, mô tả, tag, chế độ hiển thị, v.v.)
    """

    def __init__(self, url: str = None):
        self.url = url or BACKEND_URL

    def notify_completion(self, upload_id: str, file_path: str, metadata: dict):
        """
        Báo cáo với Flask rằng file upload đã hoàn tất.

        Args:
            upload_id (str): ID của file (do socket server tạo)
            file_path (str): Đường dẫn tuyệt đối nơi file được lưu
            metadata (dict): Gồm token, filename, description, visibility, tags
        """
        if not metadata:
            print(f"[BackendClient] ⚠️ Thiếu metadata cho {upload_id}")
            return

        token = metadata.get("token")
        if not token:
            print(f"[BackendClient] ⚠️ Thiếu token xác thực cho {upload_id}")
            return

        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "filename": metadata.get("filename"),
            "file_path": file_path,
            "description": metadata.get("description"),
            "visibility": metadata.get("visibility", "private"),
            "tags": metadata.get("tags", []),
        }

        # Chạy thread riêng để tránh block socket server
        thread = threading.Thread(
            target=safe_post, args=(self.url, payload, headers), daemon=True
        )
        thread.start()

        print(f"[BackendClient] 📤 Đang gửi thông báo hoàn tất cho {payload['filename']}...")
