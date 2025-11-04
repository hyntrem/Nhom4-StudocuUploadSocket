import socket
import json
import os
import time
import threading
import sys

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 6000
CHUNK_SIZE = 65536  # 64KB
STATE_FILE = 'client_upload_state.json'

lock = threading.Lock()


def send_json(sock, obj):
    """Gửi dict JSON có newline ở cuối"""
    msg = (json.dumps(obj) + "\n").encode("utf-8")
    sock.sendall(msg)


def read_json(sock):
    """Đọc một dòng JSON phản hồi từ server"""
    data = b""
    while not data.endswith(b"\n"):
        chunk = sock.recv(1)
        if not chunk:
            return None
        data += chunk
    return json.loads(data.decode("utf-8").strip())


def save_state(upload_id, offset):
    """Lưu offset hiện tại để resume"""
    with lock:
        state = {}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                try:
                    state = json.load(f)
                except Exception:
                    state = {}
        state[upload_id] = offset
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)


def load_state(upload_id):
    """Lấy offset đã lưu"""
    if not os.path.exists(STATE_FILE):
        return 0
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            return state.get(upload_id, 0)
    except Exception:
        return 0


class UploadClient:
    def __init__(self, file_path, token, description="", visibility="private", tags=None):
        self.file_path = file_path
        self.token = token
        self.description = description
        self.visibility = visibility
        self.tags = tags or []
        self.filename = os.path.basename(file_path)
        self.filesize = os.path.getsize(file_path)
        self.upload_id = f"{int(time.time())}_{self.filename}"

        self.sock = None
        self.stop_flag = False
        self.pause_flag = False
        self.thread = None

    def connect(self):
        """Kết nối tới socket server"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((SERVER_HOST, SERVER_PORT))

    def close(self):
        """Đóng kết nối"""
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass

    def start_upload(self):
        """Bắt đầu hoặc resume upload"""
        self.stop_flag = False
        self.pause_flag = False

        self.thread = threading.Thread(target=self._upload_loop, daemon=True)
        self.thread.start()

    def _upload_loop(self):
        try:
            self.connect()
            offset = load_state(self.upload_id)

            # Gửi lệnh start hoặc resume
            send_json(self.sock, {
                "action": "start" if offset == 0 else "resume",
                "upload_id": self.upload_id,
                "filename": self.filename,
                "filesize": self.filesize,
                "chunk_size": CHUNK_SIZE,
                "metadata": {
                    "token": self.token,
                    "description": self.description,
                    "visibility": self.visibility,
                    "tags": self.tags
                }
            })

            resp = read_json(self.sock)
            if not resp or resp.get("status") != "ok":
                print("❌ Lỗi khởi tạo:", resp)
                return

            offset = resp.get("offset", 0)
            print(f"🚀 Bắt đầu upload {self.filename} từ byte {offset}/{self.filesize}")

            with open(self.file_path, "rb") as f:
                while offset < self.filesize:
                    if self.stop_flag:
                        print("⛔ Dừng upload theo yêu cầu.")
                        send_json(self.sock, {"action": "stop", "upload_id": self.upload_id})
                        save_state(self.upload_id, offset)
                        break

                    if self.pause_flag:
                        print("⏸ Upload tạm dừng.")
                        send_json(self.sock, {"action": "pause", "upload_id": self.upload_id})
                        save_state(self.upload_id, offset)
                        while self.pause_flag and not self.stop_flag:
                            time.sleep(0.3)
                        if self.stop_flag:
                            break
                        print("▶️ Tiếp tục upload.")
                        send_json(self.sock, {"action": "resume", "upload_id": self.upload_id})

                    f.seek(offset)
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break

                    send_json(self.sock, {
                        "action": "chunk",
                        "upload_id": self.upload_id,
                        "offset": offset,
                        "length": len(chunk)
                    })
                    self.sock.sendall(chunk)

                    ack = read_json(self.sock)
                    if not ack or ack.get("status") != "ok":
                        print("⚠️ Lỗi khi gửi chunk:", ack)
                        save_state(self.upload_id, offset)
                        break

                    offset = ack.get("offset", offset)
                    save_state(self.upload_id, offset)
                    progress = (offset / self.filesize) * 100
                    print(f"⬆️  Tiến độ: {progress:.2f}%")

                if offset >= self.filesize:
                    print("✅ Upload hoàn tất 100%.")
                    if os.path.exists(STATE_FILE):
                        with open(STATE_FILE, "r+", encoding="utf-8") as f:
                            try:
                                data = json.load(f)
                                data.pop(self.upload_id, None)
                                f.seek(0)
                                f.truncate()
                                json.dump(data, f, indent=2)
                            except Exception:
                                pass
        except Exception as e:
            print("⚠️ Lỗi upload:", e)
        finally:
            self.close()

    def pause(self):
        """Tạm dừng"""
        self.pause_flag = True

    def resume(self):
        """Tiếp tục"""
        self.pause_flag = False

    def stop(self):
        """Dừng hoàn toàn"""
        self.stop_flag = True
        self.pause_flag = False


# ===========================
# 💡 TEST GIAO DIỆN DÒNG LỆNH
# ===========================
if __name__ == "__main__":
    token = input("Nhập token (JWT): ").strip()
    file_path = input("Nhập đường dẫn file cần upload: ").strip()

    client = UploadClient(
        file_path=file_path,
        token=token,
        description="File test upload socket",
        visibility="public",
        tags=["socket", "resume"]
    )

    client.start_upload()

    print("\nLệnh điều khiển:")
    print(" [p] pause | [r] resume | [s] stop | [q] quit\n")

    while True:
        cmd = input(">> ").strip().lower()
        if cmd == "p":
            client.pause()
        elif cmd == "r":
            client.resume()
        elif cmd == "s":
            client.stop()
        elif cmd == "q":
            client.stop()
            print("Thoát chương trình.")
            break
