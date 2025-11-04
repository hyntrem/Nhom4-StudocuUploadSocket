import json
import os
import threading
import tempfile

# Xác định đường dẫn thư mục: vd: ../tmp/uploads_state.json
BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
TMP_DIR = os.path.join(BASE_DIR, 'tmp')
os.makedirs(TMP_DIR, exist_ok=True)
STATE_FILE = os.path.join(TMP_DIR, 'uploads_state.json')
_LOCK = threading.Lock() # Khóa file

class Persistence:
    """
    Lớp xử lý việc ĐỌC và GHI file JSON trạng thái một cách an toàn.
    """
    def __init__(self, path=None):
        self.path = path or STATE_FILE # Dùng đường dẫn mặc định nếu không chỉ định

    def load(self):
        """
        Tải và phân tích (parse) file JSON trạng thái.
        Trả về {} nếu file không tồn tại hoặc bị lỗi.
        """
        with _LOCK:
            if not os.path.exists(self.path):
                return {}
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                # Nếu file JSON bị lỗi, trả về dict rỗng
                return {}

    def save(self, data):
        """
        Ghi (dump) dữ liệu (data) ra file JSON một cách an toàn.
        Sử dụng kỹ thuật ghi vào file tạm -> đổi tên file (atomic replace)
        để tránh trường hợp server crash khi đang ghi dở, làm hỏng file state.
        """
        with _LOCK:
            # 1. Tạo một file tạm
            tmpfd, tmppath = tempfile.mkstemp(dir=os.path.dirname(self.path))
            # 2. Ghi dữ liệu mới vào file tạm
            with os.fdopen(tmpfd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            # 3. Thay thế (đổi tên) file tạm thành file state chính
            os.replace(tmppath, self.path)