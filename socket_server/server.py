import socket
import os

HOST = '127.0.0.1'
PORT = 9999
BUFFER_SIZE = 4096

def get_file_size(file_path):
    """Kiểm tra kích thước file nếu nó tồn tại, không thì trả về 0."""
    if os.path.exists(file_path):
        return os.path.getsize(file_path)
    return 0

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    # Cài đặt này để cho phép tái sử dụng địa chỉ ngay lập tức
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
    
    s.bind((HOST, PORT))
    s.listen()
    print(f"Server đang lắng nghe tại {HOST}:{PORT}")
    
    while True: # Cho phép server nhận nhiều kết nối
        conn, addr = s.accept()
        with conn:
            print(f"\nĐã kết nối bởi {addr}")
            
            # -----------------------------------------------------------------
            # GIAO THỨC MỚI (HANDSHAKE)
            # -----------------------------------------------------------------
            # 1. Nhận thông tin file (Tên file và Tổng kích thước)
            #   Định dạng dự kiến: "FILENAME:file.txt|SIZE:123456"
            try:
                file_info = conn.recv(1024).decode('utf-8')
                if not file_info or "|" not in file_info:
                    raise ValueError("Không nhận được thông tin file hợp lệ")
                
                parts = dict(p.split(':') for p in file_info.split('|'))
                file_name = parts['FILENAME']
                total_size = int(parts['SIZE'])
                
                # Tạo tên file lưu trữ trên server
                server_file_path = f"uploaded_{file_name}"
                
                # 2. Kiểm tra kích thước file đã có (phục vụ resume)
                start_byte = get_file_size(server_file_path)
                
                print(f"Đang nhận file: {file_name} (Tổng: {total_size} bytes)")
                if start_byte > 0:
                    print(f"File đã tồn tại. Sẽ resume từ byte {start_byte}.")
                
                # 3. Gửi lại vị trí bắt đầu cho Client
                conn.sendall(f"START_AT:{start_byte}".encode('utf-8'))
                
                # -----------------------------------------------------------------
                # NHẬN FILE
                # -----------------------------------------------------------------
                # Mở file ở chế độ "ab" (Append Binary)
                # Đây là mấu chốt để "resume"
                bytes_da_nhan = start_byte
                with open(server_file_path, "ab") as f:
                    while bytes_da_nhan < total_size:
                        data = conn.recv(BUFFER_SIZE)
                        if not data:
                            # Client ngắt kết nối đột ngột (do lỗi mạng hoặc pause)
                            print(f"Client ngắt kết nối. Đã nhận {bytes_da_nhan} bytes.")
                            break
                        
                        f.write(data)
                        bytes_da_nhan += len(data)
                        
                        # Gửi ACK (vẫn cần thiết)
                        conn.sendall(b'ACK')
                
                if bytes_da_nhan == total_size:
                    print(f"Đã nhận xong file: {file_name}")
                else:
                    print(f"Hoàn tất phiên, chờ kết nối lại để resume.")
                    
            except Exception as e:
                print(f"Lỗi trong quá trình xử lý: {e}")