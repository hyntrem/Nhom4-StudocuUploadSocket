import threading
import time
from persistence import Persistence # Nhập module đọc/ghi file JSON

PERSIST_PATH = None  # Sẽ dùng đường dẫn mặc định từ persistence.py

class StateManager:
    """
    Lớp quản lý trạng thái của TOÀN BỘ các lượt upload.
    Nó chạy trong bộ nhớ (memory) và đồng bộ (save) xuống file JSON
    để có thể khôi phục (resume) nếu server bị restart.
    """
    def __init__(self):
        self._lock = threading.RLock() # Khóa để tránh lỗi khi nhiều luồng cùng truy cập
        # Tải trạng thái đã lưu từ file JSON (nếu có) khi server khởi động
        self._store = Persistence().load() or {}
        # Cấu trúc của _store:
        # {
        #   "upload_id_1": {"filename": "a.pdf", "filesize": 1000, "offset": 500, "state": "paused", ...},
        #   "upload_id_2": {"filename": "b.zip", "filesize": 2000, "offset": 2000, "state": "completed", ...}
        # }
    
    def _save(self):
        """Hàm nội bộ: Lưu toàn bộ trạng thái hiện tại ra file JSON."""
        Persistence().save(self._store)

    def start_upload(self, upload_id, filename, filesize, peer):
        """Được gọi khi client gửi action 'start'."""
        with self._lock:
            entry = self._store.get(upload_id)
            if not entry:
                # Nếu là file upload mới
                entry = {"filename": filename, "filesize": int(filesize), "offset": 0, "state": "sending", "last_update": time.time(), "peer": peer}
                self._store[upload_id] = entry
            else:
                # Nếu là file cũ (resume), cập nhật lại thông tin
                entry.update({"filename": filename, "filesize": int(filesize), "state": "sending", "peer": peer, "last_update": time.time()})
            self._save() # Lưu lại

    def update_offset(self, upload_id, offset):
        """Được gọi sau mỗi chunk: Cập nhật số byte đã nhận được."""
        with self._lock:
            entry = self._store.get(upload_id)
            if not entry:
                return # Bỏ qua nếu không tìm thấy (lỗi lạ)
            entry['offset'] = int(offset)
            entry['last_update'] = time.time()
            self._save() # Lưu lại

    def get_offset(self, upload_id):
        """Lấy offset (số byte đã nhận) của 1 file upload."""
        with self._lock:
            entry = self._store.get(upload_id)
            return int(entry['offset']) if entry else 0

    def get_filename(self, upload_id):
        """Lấy tên file của 1 file upload."""
        with self._lock:
            entry = self._store.get(upload_id)
            return entry['filename'] if entry else None

    def get_size(self, upload_id):
        """Lấy tổng kích thước của 1 file upload."""
        with self._lock:
            entry = self._store.get(upload_id)
            return int(entry['filesize']) if entry else 0

    def pause_upload(self, upload_id):
        """Đánh dấu 'paused'."""
        with self._lock:
            entry = self._store.get(upload_id)
            if entry:
                entry['state'] = 'paused'
                entry['last_update'] = time.time()
                self._save()

    def resume_upload(self, upload_id, peer=None):
        """Đánh dấu 'sending' (đang gửi)."""
        with self._lock:
            entry = self._store.get(upload_id)
            if entry:
                entry['state'] = 'sending'
                if peer:
                    entry['peer'] = peer # Cập nhật IP/Port của client
                entry['last_update'] = time.time()
                self._save()

    def stop_upload(self, upload_id):
        """Đánh dấu 'stopped' (bị hủy)."""
        with self._lock:
            entry = self._store.get(upload_id)
            if entry:
                entry['state'] = 'stopped'
                entry['last_update'] = time.time()
                self._save()

    def finish_upload(self, upload_id):
        """Đánh dấu 'completed' (hoàn thành)."""
        with self._lock:
            entry = self._store.get(upload_id)
            if entry:
                entry['state'] = 'completed'
                entry['last_update'] = time.time()
                self._save()