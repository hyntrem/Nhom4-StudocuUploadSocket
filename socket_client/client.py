import socket
import os
import time
from tqdm import tqdm

HOST = '127.0.0.1'
PORT = 9999
BUFFER_SIZE = 4096
FILENAME_TO_SEND = "file_can_gui.txt" 

# (Tùy chọn) Tạo file giả nếu chưa có
if not os.path.exists(FILENAME_TO_SEND):
    print(f"Tạo file giả {FILENAME_TO_SEND}")
    with open(FILENAME_TO_SEND, "w") as f:
        f.write("Noi dung file test.\n" * 1000000) # Tạo file ~ 20MB

def connect_to_server():
    """Hàm kết nối, trả về đối tượng socket."""
    print("Đang kết nối tới server...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((HOST, PORT))
        print("Đã kết nối.")
        return s
    except socket.error as e:
        print(f"Không thể kết nối: {e}")
        return None

def start_upload():
    s = None
    upload_thanh_cong = False
    
    try:
        # Lấy thông tin file
        file_name = os.path.basename(FILENAME_TO_SEND)
        file_size = os.path.getsize(FILENAME_TO_SEND)

        # -----------------------------------------------------------------
        # GIAO THỨC MỚI (HANDSHAKE)
        # -----------------------------------------------------------------
        s = connect_to_server()
        if not s:
            raise Exception("Không thể kết nối tới server.")

        # 1. Gửi thông tin file (Tên và Kích thước)
        file_info = f"FILENAME:{file_name}|SIZE:{file_size}"
        s.sendall(file_info.encode('utf-8'))

        # 2. Chờ Server phản hồi vị trí bắt đầu
        response = s.recv(BUFFER_SIZE).decode('utf-8')
        if not response.startswith("START_AT:"):
            raise Exception(f"Server phản hồi không hợp lệ: {response}")
        
        start_byte = int(response.split(':')[1])
        print(f"Server cho phép resume từ byte {start_byte}")

        # -----------------------------------------------------------------
        # GỬI FILE (từ vị trí start_byte)
        # -----------------------------------------------------------------
        with open(FILENAME_TO_SEND, 'rb') as f:
            # 3. Tua file đến vị trí start_byte
            f.seek(start_byte)
            
            # TÁC VỤ 4: Hiển thị progress bar
            # T tqdm được nâng cấp:
            #   total = Kích thước đầy đủ của file
            #   initial = Vị trí đã có (để thanh bar hiển thị đúng)
            with tqdm(total=file_size, unit='B', unit_scale=True, 
                      desc=file_name, initial=start_byte) as progress:
                
                while True:
                    chunk = f.read(BUFFER_SIZE)
                    if not chunk:
                        break # Đã đọc hết file
                    
                    s.sendall(chunk)
                    
                    # TÁC VỤ 3: Lắng nghe ACK
                    ack = s.recv(BUFFER_SIZE)
                    if not ack or ack != b'ACK':
                        raise Exception("Server lỗi hoặc không phản hồi ACK")
                    
                    progress.update(len(chunk))
        
        upload_thanh_cong = True

    except (socket.error, Exception) as e:
        print(f"\nLỖI: {e}. Quá trình upload bị gián đoạn.")
        # TÁC VỤ 5: XỬ LÝ LỖI MẠNG
        #   (Không làm gì cả, hàm sẽ kết thúc,
        #    và chúng ta sẽ gọi lại nó ở bên ngoài)
        pass # Cho phép hàm kết thúc
    
    finally:
        if s:
            s.close()
            print("Đã đóng kết nối tạm thời.")
    
    return upload_thanh_cong

# -----------------------------------------------------------------
# TÁC VỤ 5: Vòng lặp TỰ ĐỘNG RESUME
# -----------------------------------------------------------------
print("Bắt đầu trình upload...")
while True:
    thanh_cong = start_upload()
    
    if thanh_cong:
        print("\n[THÔNG BÁO: Upload thành công!]")
        break # Thoát khỏi vòng lặp
    else:
        # Nếu không thành công (do lỗi mạng), chờ 5 giây và thử lại
        print("\n[THÔNG BÁO: Upload thất bại, sẽ tự động thử lại sau 5 giây...]")
        time.sleep(5)