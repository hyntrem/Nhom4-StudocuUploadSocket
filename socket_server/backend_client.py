import os
import requests
import threading
import time

# Sửa URL: Trỏ đến API 'documents' của app.py
BACKEND_URL = os.environ.get('BACKEND_URL', 'http://127.0.0.1:5000/api/documents')
_TIMEOUT = 5 # Tăng thời gian chờ lên 5 giây

def safe_post(url, payload, headers):
    """
    Hàm helper: Thực hiện POST request với payload và headers (chứa token).
    """
    try:
        # Gửi dữ liệu JSON, đính kèm headers
        response = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
        if response.status_code == 201: # 201 Created
            print(f"BackendClient: Báo cáo hoàn thành cho {payload.get('filename')} thành công!")
        else:
            print(f"BackendClient: Lỗi khi báo cáo. Status: {response.status_code}, Body: {response.text}")
    except Exception as e:
        print(f"BackendClient: Không thể kết nối API Backend. Lỗi: {e}")

class BackendClient:
    """
    Lớp này chỉ gọi API Backend 1 LẦN DUY NHẤT khi upload hoàn tất.
    """
    def __init__(self, url=None):
        self.url = url or BACKEND_URL

    def notify_completion(self, upload_id: str, file_path: str, metadata: dict):
        """
        Gửi thông báo upload hoàn tất (tương đương với POST /api/documents).
        
        Args:
            upload_id (str): ID của file
            file_path (str): Đường dẫn đầy đủ trên server (vd: .../storage/uploads/file.pdf)
            metadata (dict): Dict chứa (token, description, visibility, tags)
        """
        if not metadata:
            print(f"BackendClient: Không thể báo cáo {upload_id} vì thiếu metadata.")
            return

        # Lấy token ra khỏi metadata để đưa vào Header
        token = metadata.get('token')
        if not token:
            print(f"BackendClient: Không thể báo cáo {upload_id} vì thiếu token.")
            return

        # Xây dựng headers chứa token
        headers = {
            "Authorization": f"Bearer {token}"
        }

        # Xây dựng payload (body) mà app.py mong đợi
        payload = {
            "filename": metadata.get('filename'),
            "file_path": file_path, # Đường dẫn mà socket server đã lưu file
            "description": metadata.get('description'),
            "visibility": metadata.get('visibility', 'private'),
            "tags": metadata.get('tags', [])
        }
        
        # Chạy trong thread riêng để không block server socket
        t = threading.Thread(target=safe_post, args=(self.url, payload, headers), daemon=True)
        t.start()