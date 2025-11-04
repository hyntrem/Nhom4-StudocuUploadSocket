"""
chunkhandler.py
---------------
Module xử lý ghi từng chunk của file được upload qua socket.

Chức năng chính:
- Tạo thư mục đích nếu chưa tồn tại
- Ghi dữ liệu nhị phân (bytes) vào vị trí offset cụ thể trong file
- Đảm bảo flush xuống đĩa an toàn
- Có xử lý lỗi và ghi log rõ ràng
"""

import os
import io

def write_chunk(path: str, data: bytes, offset: int) -> bool:
    """
    Ghi một chunk dữ liệu nhị phân vào file tại vị trí offset cụ thể.

    Args:
        path (str): Đường dẫn file cần ghi.
        data (bytes): Dữ liệu chunk.
        offset (int): Vị trí (byte offset) trong file để bắt đầu ghi.

    Returns:
        bool: True nếu ghi thành công, False nếu lỗi.
    """
    try:
        # 🔧 1. Đảm bảo thư mục tồn tại
        dir_path = os.path.dirname(path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        # 🔒 2. Mở file ở chế độ hỗ trợ ghi nhị phân có seek
        mode = "r+b" if os.path.exists(path) else "w+b"

        with open(path, mode) as f:
            f.seek(offset)
            f.write(data)
            f.flush()

            # 💾 3. Đảm bảo dữ liệu được ghi thật sự xuống ổ đĩa
            try:
                os.fsync(f.fileno())
            except OSError:
                # Một số hệ thống (Windows network drives / Docker) có thể không hỗ trợ fsync
                pass

        return True

    except (IOError, OSError) as e:
        print(f"[ChunkHandler] ❌ Lỗi khi ghi file '{path}': {e}")
        return False
    except Exception as e:
        print(f"[ChunkHandler] ⚠️ Lỗi không xác định: {e}")
        return False
