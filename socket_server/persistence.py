"""
persistence.py
---------------
Module lưu/đọc trạng thái upload an toàn (atomic JSON save).

Chức năng:
- Lưu thông tin upload đang diễn ra (upload_id, offset, status, v.v.)
- Dùng lock để đảm bảo thread-safe
- Sử dụng atomic write (ghi vào file tạm rồi thay thế)
- Tự tạo thư mục tmp/ nếu chưa có
"""

import json
import os
import threading
import tempfile
from typing import Dict, Any

# ==============================================
# 🗂️ Cấu hình thư mục và file lưu trạng thái
# ==============================================
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
os.makedirs(TMP_DIR, exist_ok=True)

STATE_FILE = os.path.join(TMP_DIR, "uploads_state.json")
_LOCK = threading.Lock()  # Khóa để tránh ghi/đọc đồng thời


# ==============================================
# 💾 Lớp xử lý lưu trữ trạng thái upload
# ==============================================
class Persistence:
    """
    Lớp xử lý việc ĐỌC và GHI file JSON trạng thái một cách an toàn.

    - Sử dụng lock nội bộ (_LOCK) để tránh race-condition giữa các luồng.
    - Sử dụng atomic replace (os.replace) để tránh hỏng file khi ghi dở.
    """

    def __init__(self, path: str = None):
        self.path = path or STATE_FILE  # Cho phép override khi test

    # ------------------------------
    def load(self) -> Dict[str, Any]:
        """
        Đọc file JSON trạng thái.
        Trả về dict rỗng nếu file không tồn tại hoặc bị lỗi.
        """
        with _LOCK:
            if not os.path.exists(self.path):
                return {}
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
                    else:
                        print("[Persistence] ⚠️ File trạng thái không đúng định dạng JSON.")
                        return {}
            except json.JSONDecodeError:
                print("[Persistence] ⚠️ Lỗi phân tích JSON (file bị hỏng). Trả về rỗng.")
                return {}
            except Exception as e:
                print(f"[Persistence] ❌ Lỗi khi đọc file trạng thái: {e}")
                return {}

    # ------------------------------
    def save(self, data: Dict[str, Any]) -> bool:
        """
        Ghi dữ liệu ra file JSON một cách an toàn (atomic write).

        Args:
            data (dict): Dữ liệu trạng thái (vd: {"upload_1": {"offset": 1024, ...}})
        Returns:
            bool: True nếu ghi thành công, False nếu có lỗi.
        """
        with _LOCK:
            try:
                # 1️⃣ Tạo file tạm
                tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(self.path))
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                # 2️⃣ Đổi tên (atomic replace)
                os.replace(tmp_path, self.path)
                return True

            except Exception as e:
                print(f"[Persistence] ❌ Lỗi khi ghi file trạng thái: {e}")
                return False

    # ------------------------------
    def update(self, upload_id: str, info: Dict[str, Any]):
        """
        Cập nhật thông tin của 1 upload cụ thể trong file JSON.

        Args:
            upload_id (str): ID của phiên upload.
            info (dict): Dữ liệu cần cập nhật (vd: {"offset": 2048, "status": "paused"}).
        """
        data = self.load()
        data[upload_id] = info
        self.save(data)
        print(f"[Persistence] 💾 Đã cập nhật trạng thái upload {upload_id}.")

    # ------------------------------
    def get(self, upload_id: str) -> Dict[str, Any]:
        """
        Lấy thông tin của một upload cụ thể.
        """
        data = self.load()
        return data.get(upload_id, {})

    # ------------------------------
    def delete(self, upload_id: str):
        """
        Xóa thông tin upload cụ thể (vd: khi upload hoàn tất).
        """
        data = self.load()
        if upload_id in data:
            del data[upload_id]
            self.save(data)
            print(f"[Persistence] 🗑️ Đã xóa trạng thái upload {upload_id}.")
