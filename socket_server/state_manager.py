import socket
import threading
import json
import os
import time
import traceback
import sys
from typing import Optional

# Đảm bảo Python tìm thấy các module trong cùng thư mục
sys.path.insert(0, os.path.dirname(__file__))

# ==============================
# 📦 IMPORT MODULES
# ==============================
try:
    from state_manager import StateManager
    from chunkhandler import write_chunk
    from backend_client import BackendClient
except Exception as e:
    print("❌ LỖI: không thể nhập các module phụ:", e)
    traceback.print_exc()
    raise

# ==============================
# ⚙️ CẤU HÌNH SERVER
# ==============================
HOST = "0.0.0.0"
PORT = 6000
BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
STORAGE_DIR = os.path.join(BASE_DIR, "storage", "uploads")
os.makedirs(STORAGE_DIR, exist_ok=True)

state = StateManager()
backend = BackendClient()

# ==============================
# 🔧 HÀM TIỆN ÍCH
# ==============================
def send_json(conn: socket.socket, obj: dict) -> bool:
    """Gửi dict (JSON) qua socket, có ký tự '\n' để client phân biệt."""
    try:
        data = (json.dumps(obj) + "\n").encode("utf-8")
        conn.sendall(data)
        return True
    except Exception:
        return False


def safe_read_exact(f, n: int) -> Optional[bytes]:
    """Đọc chính xác n bytes từ stream (ngăn lỗi thiếu chunk)."""
    parts, remaining = [], n
    while remaining > 0:
        chunk = f.read(remaining)
        if not chunk:
            return None
        parts.append(chunk)
        remaining -= len(chunk)
    return b"".join(parts)


# ==============================
# 🧠 HÀM XỬ LÝ MỖI CLIENT
# ==============================
def handle_client(conn: socket.socket, addr):
    peer = f"{addr[0]}:{addr[1]}"
    f = conn.makefile("rb")
    print(f"🔌 Client mới: {peer}")

    try:
        while True:
            line = f.readline()
            if not line:
                print(f"❎ {peer} đã ngắt kết nối.")
                break

            try:
                header = json.loads(line.decode("utf-8").strip())
            except Exception:
                send_json(conn, {"status": "error", "reason": "invalid_header"})
                continue

            action = header.get("action")
            upload_id = header.get("upload_id")
            if not upload_id:
                send_json(conn, {"status": "error", "reason": "missing_upload_id"})
                continue

            # ==============================
            # 🎬 ACTION HANDLING
            # ==============================
            try:
                # --- START ---
                if action == "start":
                    filename = header.get("filename")
                    filesize = int(header.get("filesize", 0))
                    chunk_size = int(header.get("chunk_size", 65536))
                    metadata = header.get("metadata", {})  # có thể chứa token, mô tả, tag...

                    if not filename or filesize <= 0:
                        send_json(conn, {"status": "error", "reason": "invalid_start_params"})
                        continue

                    # Ghi nhận state
                    state.start_upload(upload_id, filename, filesize, peer)
                    offset = state.get_offset(upload_id)

                    # Gửi phản hồi cho client
                    send_json(conn, {
                        "status": "ok",
                        "upload_id": upload_id,
                        "offset": offset,
                        "chunk_size": chunk_size
                    })

                # --- CHUNK ---
                elif action == "chunk":
                    length = int(header.get("length", 0))
                    offset = int(header.get("offset", 0))
                    if length <= 0:
                        send_json(conn, {"status": "error", "reason": "invalid_length"})
                        continue

                    data = safe_read_exact(f, length)
                    if data is None:
                        print(f"⚠️ Mất kết nối giữa chừng từ {peer}")
                        break

                    filename = state.get_filename(upload_id)
                    if not filename:
                        send_json(conn, {"status": "error", "reason": "unknown_upload"})
                        continue

                    # Xác định nơi lưu file
                    save_dir = os.path.join(STORAGE_DIR, upload_id)
                    os.makedirs(save_dir, exist_ok=True)
                    file_path = os.path.join(save_dir, filename)

                    # Ghi chunk
                    if not write_chunk(file_path, data, offset):
                        send_json(conn, {"status": "error", "reason": "write_failed"})
                        continue

                    # Cập nhật offset
                    new_offset = offset + length
                    state.update_offset(upload_id, new_offset)

                    # Phản hồi ACK
                    send_json(conn, {"status": "ok", "offset": new_offset})

                    # Nếu đã đủ dung lượng
                    if new_offset >= state.get_size(upload_id):
                        state.finish_upload(upload_id)
                        print(f"✅ Hoàn thành upload {upload_id}: {filename}")

                        # Gọi BackendClient báo hoàn tất
                        metadata = header.get("metadata", {})
                        metadata["filename"] = filename
                        backend.notify_completion(upload_id, file_path, metadata)

                # --- PAUSE ---
                elif action == "pause":
                    state.pause_upload(upload_id)
                    send_json(conn, {"status": "ok", "upload_id": upload_id, "state": "paused"})
                    print(f"⏸ Upload {upload_id} đã tạm dừng.")

                # --- RESUME ---
                elif action == "resume":
                    offset = state.get_offset(upload_id)
                    state.resume_upload(upload_id, peer)
                    send_json(conn, {"status": "ok", "upload_id": upload_id, "offset": offset})
                    print(f"▶️ Upload {upload_id} đã tiếp tục từ offset {offset}.")

                # --- STOP ---
                elif action == "stop":
                    state.stop_upload(upload_id)
                    send_json(conn, {"status": "ok", "upload_id": upload_id, "state": "stopped"})
                    print(f"⛔ Upload {upload_id} đã dừng.")

                # --- QUERY RESUME ---
                elif action == "query_resume":
                    offset = state.get_offset(upload_id)
                    send_json(conn, {"status": "ok", "upload_id": upload_id, "offset": offset})

                else:
                    send_json(conn, {"status": "error", "reason": "unknown_action"})

            except Exception as inner:
                print(f"❌ Lỗi khi xử lý {peer}: {inner}")
                traceback.print_exc()
                send_json(conn, {"status": "error", "reason": "internal_server_error"})

    except Exception as ex:
        print(f"🔥 Lỗi client {peer}: {ex}")
        traceback.print_exc()
    finally:
        try:
            f.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        print(f"🧹 Dọn dẹp kết nối cho {peer}")


# ==============================
# 🖥️ MAIN SERVER LOOP
# ==============================
def accept_loop():
    """Lắng nghe kết nối mới và tạo thread xử lý."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(16)
        print(f"🚀 Socket server đang chạy tại {HOST}:{PORT}")

        while True:
            try:
                conn, addr = s.accept()
                threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
            except KeyboardInterrupt:
                print("🛑 Đang tắt server...")
                break
            except Exception as e:
                print(f"⚠️ Lỗi accept_loop: {e}")
                traceback.print_exc()
                time.sleep(0.2)


if __name__ == "__main__":
    accept_loop()
