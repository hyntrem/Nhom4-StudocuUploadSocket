# ...existing code...
import socket
import threading
import json
import os
import time
import traceback
import sys
from typing import Optional

# Đảm bảo Python tìm thấy các module trong thư mục hiện tại
sys.path.insert(0, os.path.dirname(__file__))

try:
    # Nhập các module con
    from state_manager import StateManager
    from chunk_handler import write_chunk
    from backend_client import BackendClient
except Exception as e:
    print("LỖI: không thể nhập các module phụ:", e)
    traceback.print_exc()
    raise

# --- CẤU HÌNH SERVER ---
HOST = '0.0.0.0'  # Lắng nghe trên tất cả các địa chỉ IP
PORT = 6000       # Cổng lắng nghe (LƯU Ý: cần khớp với file .env)
BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
# Thư mục để lưu file upload (vd: ../storage/uploads)
STORAGE_DIR = os.path.join(BASE_DIR, 'storage', 'uploads')
os.makedirs(STORAGE_DIR, exist_ok=True) # Tạo thư mục nếu chưa có

# Khởi tạo các đối tượng quản lý (sẽ dùng cho mọi kết nối)
state = StateManager()       # Quản lý trạng thái (pause, resume, offset...)
backend = BackendClient()    # Giao tiếp với API Backend (Flask)

def send_json(conn: socket.socket, obj: dict) -> bool:
    """
    Hàm helper: Gửi một đối tượng Python (dict) dưới dạng JSON qua socket.
    Thêm ký tự '\n' để client biết đâu là kết thúc một tin nhắn.
    """
    try:
        # Chuyển dict -> string JSON -> bytes UTF-8
        data = (json.dumps(obj) + '\n').encode('utf-8')
        conn.sendall(data)
        return True
    except Exception as e:
        # Nếu gửi lỗi (client ngắt kết nối), báo lỗi và trả về False
        print(f"Lỗi send_json: {e}")
        return False

def safe_read_exact(f, n: int) -> Optional[bytes]:
    """
    Hàm helper: Đọc chính xác N-bytes từ một kết nối (file-like object).
    Hữu ích để đọc nội dung chunk mà không bị thiếu.
    """
    parts = []
    remaining = n
    while remaining > 0:
        chunk = f.read(remaining)
        if not chunk: # Nếu client ngắt kết nối giữa chừng
            return None
        parts.append(chunk)
        remaining -= len(chunk)
    return b''.join(parts) # Ghép các phần lại

def handle_client(conn: socket.socket, addr):
    """
    Hàm xử lý chính: Mỗi client kết nối sẽ được chạy trong 1 luồng (thread) riêng.
    Hàm này xử lý toàn bộ logic giao tiếp với 1 client.
    """
    peer = f"{addr[0]}:{addr[1]}" # Lấy địa chỉ IP:PORT của client
    # conn.makefile('rb') biến socket thành 1 file-object, cho phép ta dùng f.readline()
    f = conn.makefile('rb')
    print(f"Client mới kết nối từ {peer}")
    try:
        # Vòng lặp chính: Liên tục đọc tin nhắn từ client
        while True:
            line = f.readline() # Đọc "header" (là 1 dòng JSON)
            if not line:
                # Nếu không đọc được gì -> client đã ngắt kết nối
                print(f"Client {peer} đã ngắt kết nối.")
                break
            
            # --- Xử lý Header (tin nhắn JSON) ---
            try:
                header = json.loads(line.decode('utf-8').strip())
            except Exception:
                send_json(conn, {"status": "error", "reason": "invalid_header"})
                continue # Bỏ qua tin nhắn lỗi, đợi tin nhắn tiếp

            action = header.get('action')     # Hành động client muốn (start, chunk, pause...)
            upload_id = header.get('upload_id') # ID duy nhất của file upload

            if not upload_id:
                send_json(conn, {"status": "error", "reason": "missing_upload_id"})
                continue

            try:
                # --- PHÂN LOẠI HÀNH ĐỘNG ---

                if action == 'start':
                    # Client muốn bắt đầu một file upload mới
                    filename = header.get('filename')
                    filesize = int(header.get('filesize', 0))
                    chunk_size = int(header.get('chunk_size', 65536))
                    if not filename or filesize <= 0:
                        send_json(conn, {"status": "error", "reason": "invalid_start_params"})
                        continue
                    
                    # 1. Lưu trạng thái bắt đầu
                    state.start_upload(upload_id, filename, filesize, peer)
                    offset = state.get_offset(upload_id) # Lấy offset (thường là 0, hoặc khác 0 nếu là resume)
                    # 2. Báo cho API Backend biết
                    backend.update(upload_id, 'started', offset, filesize)
                    # 3. Trả lời client, báo offset hiện tại để client biết gửi từ đâu
                    send_json(conn, {"status": "ok", "upload_id": upload_id, "offset": offset, "chunk_size": chunk_size})

                elif action == 'chunk':
                    # Client đang gửi một phần (chunk) của file
                    length = int(header.get('length', 0)) # Kích thước chunk
                    offset = int(header.get('offset', 0)) # Vị trí bắt đầu ghi
                    if length <= 0:
                        send_json(conn, {"status": "error", "reason": "invalid_length"})
                        continue
                    
                    # 1. Đọc chính xác N-bytes (nội dung file)
                    data = safe_read_exact(f, length)
                    if data is None or len(data) != length:
                        # Client ngắt kết nối khi đang gửi dở chunk
                        print(f"Chunk không hoàn chỉnh từ {peer} (upload_id={upload_id})")
                        break # Thoát vòng lặp, đóng kết nối
                    
                    filename = state.get_filename(upload_id) # Lấy tên file từ state
                    if filename is None:
                        send_json(conn, {"status": "error", "reason": "unknown_upload"})
                        continue
                    
                    # 2. Xác định đường dẫn lưu file
                    file_path = os.path.join(STORAGE_DIR, filename)
                    try:
                        # 3. Ghi chunk này xuống đĩa
                        write_chunk(file_path, data, offset)
                    except Exception as we:
                        print(f"Lỗi ghi file: {we}")
                        send_json(conn, {"status": "error", "reason": "write_failed"})
                        continue
                    
                    # 4. Cập nhật offset mới
                    new_offset = offset + length
                    state.update_offset(upload_id, new_offset)
                    # 5. Báo cáo tiến độ cho API Backend
                    backend.update(upload_id, 'uploading', new_offset, state.get_size(upload_id))
                    # 6. Gửi ACK (xác nhận) cho client, báo offset mới
                    send_json(conn, {"status": "ok", "offset": new_offset})

                    # 7. Kiểm tra xem đã upload xong 100% chưa
                    if new_offset >= state.get_size(upload_id):
                        state.finish_upload(upload_id) # Đánh dấu hoàn thành
                        backend.update(upload_id, 'completed', new_offset, state.get_size(upload_id))
                        print(f"--- Hoàn thành Upload: {upload_id} -> {filename} ---")

                elif action == 'pause':
                    # Client nhấn nút Tạm dừng
                    state.pause_upload(upload_id)
                    backend.update(upload_id, 'paused', state.get_offset(upload_id), state.get_size(upload_id))
                    send_json(conn, {"status": "ok", "upload_id": upload_id, "state": "paused"})

                elif action == 'resume':
                    # Client nhấn nút Tiếp tục
                    offset = state.get_offset(upload_id)
                    state.resume_upload(upload_id, peer)
                    backend.update(upload_id, 'resumed', offset, state.get_size(upload_id))
                    send_json(conn, {"status": "ok", "upload_id": upload_id, "offset": offset})

                elif action == 'stop':
                    # Client nhấn nút Dừng (hủy)
                    state.stop_upload(upload_id)
                    backend.update(upload_id, 'stopped', state.get_offset(upload_id), state.get_size(upload_id))
                    send_json(conn, {"status": "ok", "upload_id": upload_id, "state": "stopped"})

                elif action == 'query_resume':
                    # Client vừa kết nối lại, hỏi xem file này đã upload tới đâu
                    offset = state.get_offset(upload_id)
                    send_json(conn, {"status": "ok", "upload_id": upload_id, "offset": offset})

                else:
                    # Client gửi action lạ
                    send_json(conn, {"status": "error", "reason": "unknown_action"})
            except Exception as inner:
                print(f"Lỗi khi xử lý {peer}: {inner}")
                traceback.print_exc()
                try:
                    send_json(conn, {"status": "error", "reason": "internal_server_error"})
                except Exception:
                    pass # Client có thể đã ngắt kết nối rồi
    except Exception as ex:
        # Lỗi ở vòng lặp ngoài (ví dụ: lỗi mạng nghiêm trọng)
        print(f"Lỗi Client handler: {ex}")
        traceback.print_exc()
    finally:
        # Dọn dẹp
        try:
            f.close()
        except Exception:
            pass
        try:
            conn.close() # Đóng kết nối socket
        except Exception:
            pass
        print(f"Dọn dẹp kết nối cho {peer}")

def accept_loop():
    """
    Hàm khởi động server: Vòng lặp vô hạn để chấp nhận kết nối mới.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Cho phép tái sử dụng địa chỉ
        s.bind((HOST, PORT)) # Gắn server vào địa chỉ và cổng
        s.listen(16) # Bắt đầu lắng nghe
        print(f"Socket server đang lắng nghe trên {HOST}:{PORT}")
        while True:
            try:
                conn, addr = s.accept() # Chấp nhận kết nối mới (blocking)
                # Tạo một luồng mới để xử lý client này, giải phóng vòng lặp
                t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
                t.start()
            except KeyboardInterrupt:
                print("Đang tắt server...")
                break # Thoát vòng lặp nếu nhấn Ctrl+C
            except Exception as e:
                print(f"Lỗi accept_loop: {e}")
                traceback.print_exc()
                time.sleep(0.1)

if __name__ == '__main__':
    accept_loop() # Chạy server
# ...existing code...
