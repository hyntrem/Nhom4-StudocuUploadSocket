# ==============================
# 🚀 SERVER TCP SOCKET (Bản chạy được với client.py)
# ==============================
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
    from persistence import Persistence
    from chunk_handler import write_chunk
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

state = Persistence()
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
def recv_line(conn: socket.socket, maxlen=65536) -> Optional[bytes]:
    """Đọc tới newline (\n) — trả về None nếu kết nối đóng hoặc lỗi."""
    buf = bytearray()
    while True:
        try:
            chunk = conn.recv(1)
        except socket.timeout:
            return None
        except ConnectionResetError:
            return None
        if not chunk:
            return None
        buf += chunk
        if buf.endswith(b'\n') or len(buf) >= maxlen:
            return bytes(buf)
    # unreachable

def recv_exact(conn: socket.socket, n: int) -> Optional[bytes]:
    """Đọc chính xác n bytes từ socket (blocking), trả None nếu EOF/timeout/reset."""
    parts = []
    remaining = n
    while remaining > 0:
        try:
            chunk = conn.recv( min(65536, remaining) )
        except socket.timeout:
            return None
        except ConnectionResetError:
            return None
        if not chunk:
            return None
        parts.append(chunk)
        remaining -= len(chunk)
    return b"".join(parts)

def handle_client(conn: socket.socket, addr):
    peer = f"{addr[0]}:{addr[1]}"
    print(f"🔌 Client mới: {peer}")
    # timeout: nếu client im lặng quá lâu sẽ văng ra None từ recv_line/recv_exact
    conn.settimeout(60)  # điều chỉnh hợp lý: 30-120s tùy usecase

    try:
        while True:
            line = recv_line(conn)
            if not line:
                print(f"❎ {peer} đã ngắt kết nối (no header).")
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

            try:
                if action == "start":
                    filename = header.get("filename")
                    filesize = int(header.get("filesize", 0))
                    chunk_size = int(header.get("chunk_size", 65536))
                    metadata = header.get("metadata", {})
                    if not filename or filesize <= 0:
                        send_json(conn, {"status": "error", "reason": "invalid_start_params"})
                        continue

                    info = state.get(upload_id)
                    if not info:
                        info = {
                            "filename": filename,
                            "filesize": filesize,
                            "offset": 0,
                            "status": "started",
                            "peer": peer,
                            "metadata": metadata,
                            "created_at": time.time()
                        }
                    else:
                        info["peer"] = peer
                        info["status"] = "resumed"

                    state.update(upload_id, info)
                    offset = info.get("offset", 0)
                    send_json(conn, {"status": "ok", "upload_id": upload_id, "offset": offset, "chunk_size": chunk_size})

                elif action == "chunk":
                    length = int(header.get("length", 0))
                    offset = int(header.get("offset", 0))
                    if length <= 0:
                        send_json(conn, {"status": "error", "reason": "invalid_length"})
                        continue

                    data = recv_exact(conn, length)
                    if data is None:
                        print(f"⚠️ Mất kết nối giữa chừng từ {peer} khi đọc chunk (expected={length}).")
                        break

                    info = state.get(upload_id)
                    if not info:
                        send_json(conn, {"status": "error", "reason": "unknown_upload"})
                        continue

                    filename = info.get("filename")
                    save_dir = os.path.join(STORAGE_DIR, upload_id)
                    os.makedirs(save_dir, exist_ok=True)
                    file_path = os.path.join(save_dir, filename)

                    if not write_chunk(file_path, data, offset):
                        send_json(conn, {"status": "error", "reason": "write_failed"})
                        continue

                    new_offset = offset + length
                    info["offset"] = new_offset
                    info["status"] = "uploading"
                    state.update(upload_id, info)

                    send_json(conn, {"status": "ok", "offset": new_offset})

                    if new_offset >= info.get("filesize", 0):
                        print(f"✅ Hoàn thành upload {upload_id}: {filename}")
                        full_metadata = info.get("metadata", {})
                        if "filename" not in full_metadata:
                            full_metadata["filename"] = filename
                        backend.notify_completion(upload_id, file_path, full_metadata)
                        state.delete(upload_id)

                elif action == "pause":
                    info = state.get(upload_id); info["status"] = "paused"; state.update(upload_id, info)
                    send_json(conn, {"status": "ok", "upload_id": upload_id, "state": "paused"})
                    print(f"⏸ Upload {upload_id} đã tạm dừng.")

                elif action == "resume":
                    info = state.get(upload_id)
                    info["status"] = "resumed"; info["peer"] = peer
                    state.update(upload_id, info)
                    offset = info.get("offset", 0)
                    send_json(conn, {"status": "ok", "upload_id": upload_id, "offset": offset})
                    print(f"▶️ Upload {upload_id} đã tiếp tục từ offset {offset}.")

                elif action == "stop":
                    info = state.get(upload_id); info["status"] = "stopped"; state.update(upload_id, info)
                    send_json(conn, {"status": "ok", "upload_id": upload_id, "state": "stopped"})
                    print(f"⛔ Upload {upload_id} đã dừng.")

                elif action == "query_resume":
                    offset = state.get(upload_id).get("offset", 0)
                    send_json(conn, {"status": "ok", "upload_id": upload_id, "offset": offset})

                else:
                    send_json(conn, {"status": "error", "reason": "unknown_action"})

            except Exception as inner:
                print(f"❌ Lỗi khi xử lý {peer}: {inner}")
                traceback.print_exc()
                try:
                    send_json(conn, {"status": "error", "reason": "internal_server_error"})
                except Exception:
                    pass

    except ConnectionResetError as cre:
        print(f"🔥 ConnectionResetError từ {peer}: {cre}")
    except Exception as ex:
        print(f"🔥 Lỗi client {peer}: {ex}")
        traceback.print_exc()
    finally:
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
        print(f"🚀 Socket server (TCP) đang chạy tại {HOST}:{PORT}")

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
    try:
        accept_loop()
    except KeyboardInterrupt:
        print("🛑 Đang tắt server...")