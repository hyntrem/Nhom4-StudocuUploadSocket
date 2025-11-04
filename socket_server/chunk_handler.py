# ...existing code...
import os

def write_chunk(path, data: bytes, offset: int):
    """
    Ghi chunk bytes vào file tại vị trí offset.
    Tạo thư mục nếu cần; mở file ở chế độ binary, seek rồi write.
    Chắc chắn fsync để dữ liệu flush xuống đĩa.
    """
    # ensure directory exists
    dirp = os.path.dirname(path)
    if dirp:
        os.makedirs(dirp, exist_ok=True)
    # open low-level to support seeking beyond current EOF
    mode = 'r+b' if os.path.exists(path) else 'w+b'
    with open(path, mode) as f:
        f.seek(offset)
        f.write(data)
        f.flush()
        try:
            os.fsync(f.fileno())
        except Exception:
            # trên một số môi trường fsync có thể thất bại; không gây crash
            pass
# ...existing code...