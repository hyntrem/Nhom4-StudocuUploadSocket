USE studocu_db;

-- XÓA DỮ LIỆU CŨ (đảm bảo sạch trước khi seed)
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE document_tags;
TRUNCATE TABLE tags;
TRUNCATE TABLE documents;
TRUNCATE TABLE users;
SET FOREIGN_KEY_CHECKS = 1;

INSERT INTO users (name, email, password_hash, role, status)
VALUES
('Thanh Tâm', 'tam@example.com', '123456', 'user', 'active'),
('Huyền Trâm', 'tram@example.com', '123456', 'user', 'active'),
('Văn Nguyên', 'vnguyen@example.com', '123456', 'user', 'active'),
('Văn Long', 'long@example.com', '123456', 'user', 'inactive');
('Trung Nguyên','tnguyen@example.com', '123456', 'user', 'inactive');

INSERT INTO tags (name)
VALUES
('Cơ sở dữ liệu'),
('Lập trình mạng'),
('Phân tích hệ thống'),
('Python'),
('Kỹ thuật phần mềm');

INSERT INTO documents (filename, file_path, user_id, description, visibility, status)
VALUES
('DoAn_LapTrinhMang.pdf', '/uploads/DoAn_LapTrinhMang.pdf', 1, 'Đồ án Lập trình mạng nhóm 4 - có hướng dẫn chi tiết.', 'public', 'uploaded'),
('PhanTichHeThong.docx', '/uploads/PhanTichHeThong.docx', 2, 'Tài liệu phân tích hệ thống phần mềm', 'public', 'uploaded'),
('BaiTap_CoSoDuLieu.pdf', '/uploads/BaiTap_CoSoDuLieu.pdf', 3, 'Bài tập mẫu môn Cơ sở dữ liệu', 'private', 'uploaded'),
('HuongDan_Python.docx', '/uploads/HuongDan_Python.docx', 2, 'Tài liệu nhập môn Python', 'public', 'uploaded');

INSERT INTO document_tags (document_id, tag_id)
VALUES
(1, 2), -- Lập trình mạng
(2, 3), -- Phân tích hệ thống
(3, 1), -- Cơ sở dữ liệu
(4, 4); -- Python

SELECT '✅ Dữ liệu mẫu đã được thêm thành công!' AS message;
