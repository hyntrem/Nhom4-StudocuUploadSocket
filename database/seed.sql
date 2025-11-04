USE upload_file;

-- XÓA DỮ LIỆU CŨ
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE document_tags;
TRUNCATE TABLE tags;
TRUNCATE TABLE documents;
TRUNCATE TABLE users;
SET FOREIGN_KEY_CHECKS = 1;

-- ================= USERS =================
-- tất cả người dùng đăng nhập bằng mật khẩu: 12345
INSERT INTO users (name, email, password_hash) VALUES
('Thanh Tâm', 'tam@example.com', '$2b$12$zoNxPi34sn3DjIcAxHPA/OebNLbARQJ6L3yZEDnvzf7G920p5tirC'),
('Huyền Trâm', 'tram@example.com', '$2b$12$zoNxPi34sn3DjIcAxHPA/OebNLbARQJ6L3yZEDnvzf7G920p5tirC'),
('Vũ Nguyên', 'vnguyen@example.com', '$2b$12$zoNxPi34sn3DjIcAxHPA/OebNLbARQJ6L3yZEDnvzf7G920p5tirC'),
('Văn Long', 'long@example.com', '$2b$12$zoNxPi34sn3DjIcAxHPA/OebNLbARQJ6L3yZEDnvzf7G920p5tirC'),
('Trung Nguyên', 'tnguyen@example.com', '$2b$12$zoNxPi34sn3DjIcAxHPA/OebNLbARQJ6L3yZEDnvzf7G920p5tirC');

-- ================= TAGS =================
INSERT INTO tags (name) VALUES
('Cơ sở dữ liệu'),
('Lập trình mạng'),
('Phân tích hệ thống'),
('Python'),
('Công nghệ phần mềm');

-- ================= DOCUMENTS =================
INSERT INTO documents (filename, file_path, user_id, description, visibility, status) VALUES
('DoAn_LapTrinhMang.pdf', '/uploads/DoAn_LapTrinhMang.pdf', 1, 'Đồ án Lập trình mạng nhóm 4 - có hướng dẫn chi tiết.', 'public', 'uploaded'),
('PhanTichHeThong.docx', '/uploads/PhanTichHeThong.docx', 2, 'Tài liệu phân tích hệ thống phần mềm', 'public', 'uploaded'),
('BaiTap_CoSoDuLieu.pdf', '/uploads/BaiTap_CoSoDuLieu.pdf', 3, 'Bài tập mẫu môn Cơ sở dữ liệu', 'private', 'uploaded'),
('HuongDan_Python.docx', '/uploads/HuongDan_Python.docx', 2, 'Tài liệu nhập môn Python', 'public', 'uploaded');

-- ================= DOCUMENT_TAGS =================
INSERT INTO document_tags (document_id, tag_id) VALUES
(1, 2), -- Lập trình mạng
(2, 3), -- Phân tích hệ thống
(3, 1), -- Cơ sở dữ liệu
(4, 4); -- Python

SELECT ' Dữ liệu mẫu đã được thêm thành công! Bạn có thể đăng nhập bằng mật khẩu 12345' AS message;
