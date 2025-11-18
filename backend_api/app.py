# ==========================================================
# 📁 app.py – Flask Backend cho hệ thống Upload tài liệu Studocu
# ==========================================================

import os
import jwt
import datetime
import secrets
import string
import smtplib
import redis
from functools import wraps
from email.mime.text import MIMEText
from flask import (
    Flask, request, jsonify, make_response, send_from_directory
)
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from dotenv import load_dotenv
from flask_socketio import SocketIO
import socket as py_socket # Đổi tên để tránh xung đột
import threading
import json
from sqlalchemy import or_, func

# ==========================================================
# 🔧 CẤU HÌNH CƠ BẢN
# ==========================================================
load_dotenv()

app = Flask(__name__)
CORS(app)

# Secret Key
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secretkey')

# Cấu hình MySQL (qua XAMPP)
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASS = os.environ.get('DB_PASS', '')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'upload_file')
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}'

# Đồng bộ thư mục uploads với socket server (../storage/uploads)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, '..', 'storage', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Email cấu hình (dùng để gửi OTP)
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'youremail@gmail.com')
APP_PASSWORD = os.environ.get('APP_PASSWORD', 'yourapppassword')

# Redis config
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

# ==========================================================
# ⚙️ KHỞI TẠO CÁC MODULE HỖ TRỢ
# ==========================================================
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
# Cấu hình SocketIO làm cầu nối
socketio = SocketIO(app, cors_allowed_origins="*")

# Nơi mà server.py (TCP) đang chạy
TCP_SERVER_HOST = '127.0.0.1'
TCP_SERVER_PORT = 6000
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()
    print("✅ Kết nối Redis thành công!")
except redis.exceptions.ConnectionError as e:
    print(f"⚠️ Lỗi Redis: {e}")
    r = None

# ==========================================================
# 🧱 DATABASE MODELS
# ==========================================================
document_tags = db.Table('document_tags',
    db.Column('document_id', db.Integer, db.ForeignKey('documents.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)
class UserDocumentView(db.Model):
    __tablename__ = 'user_document_views'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), primary_key=True)
    last_viewed_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('view_history', lazy='dynamic'))
    document = db.relationship('Document', backref=db.backref('view_history', lazy='dynamic'))

class UserFavorite(db.Model):
    __tablename__ = 'user_favorites'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('favorites', lazy='dynamic'))
    document = db.relationship('Document', backref=db.backref('favorited_by', lazy='dynamic'))
    
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    documents = db.relationship('Document', backref='owner', lazy=True)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    description = db.Column(db.Text, nullable=True)
    visibility = db.Column(db.Enum('public', 'private'), default='private')
    status = db.Column(db.String(50), default='uploaded')
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    tags = db.relationship('Tag', secondary=document_tags, lazy='subquery',
                           backref=db.backref('documents', lazy=True))

class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

# ==========================================================
# 🔐 JWT DECORATOR
# ==========================================================
def record_view(user, document): 
    try: 
        view = UserDocumentView.query.filter_by(
            user_id=user.id, 
            document_id=document.id
        ).first()
        
        if view: 
            view.last_viewed_at = datetime.datetime.utcnow()
        else: 
            view = UserDocumentView(user_id=user.id, document_id=document.id)
            db.session.add(view)
         
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Lỗi khi ghi lại lượt xem: {e}")

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]

        if not token:
            return jsonify({'message': 'Token missing!'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'message': 'User not found!'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token!'}), 401

        return f(current_user, *args, **kwargs)
    return decorated

# ==========================================================
# 👤 AUTHENTICATION APIs
# ==========================================================
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    name, email, password = data.get('name'), data.get('email'), data.get('password')
    if not name or not email or not password:
        return jsonify({'message': 'Thiếu thông tin'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Email đã tồn tại'}), 409

    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'Đăng ký thành công!'}), 201


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email, password = data.get('email'), data.get('password')

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'message': 'Sai email hoặc mật khẩu'}), 401

    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({
        'message': 'Đăng nhập thành công',
        'token': token,
        'user': {'id': user.id, 'name': user.name, 'email': user.email}
    }), 200


@app.route('/api/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    data = request.get_json()
    if not current_user.check_password(data.get('old_password')):
        return jsonify({'message': 'Mật khẩu cũ không đúng'}), 400
    current_user.set_password(data.get('new_password'))
    db.session.commit()
    return jsonify({'message': 'Đổi mật khẩu thành công'}), 200


@app.route('/api/me', methods=['GET'])
@token_required
def me(current_user):
    return jsonify({
        'id': current_user.id,
        'name': current_user.name,
        'email': current_user.email
    }), 200

# ==========================================================
# 📧 OTP QUA EMAIL (REDIS)
# ==========================================================
@app.route('/send-otp', methods=['POST'])
def send_otp():
    if not r:
        return jsonify({"error": "Redis unavailable"}), 503
    email = request.json.get("email")
    if not email:
        return jsonify({"error": "Missing email"}), 400
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "Email không tồn tại"}), 404

    otp = ''.join(secrets.choice(string.digits) for _ in range(6))
    r.setex(f"otp:{email}", 300, otp)

    try:
        msg = MIMEText(f"Your OTP code is {otp}. It expires in 5 minutes.", "plain", "utf-8")
        msg["Subject"] = "OTP Code"
        msg["From"] = SENDER_EMAIL
        msg["To"] = email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, email, msg.as_string())
        return jsonify({"message": "OTP sent"}), 200
    except Exception as e:
        print(f"Email error: {e}")
        return jsonify({"error": "Failed to send email"}), 500


@app.route('/reset-password', methods=['POST'])
def reset_password():
    if not r:
        return jsonify({"error": "Redis unavailable"}), 503
    data = request.get_json()
    email, otp, new_password = data.get('email'), data.get('otp'), data.get('new_password')
    saved_otp = r.get(f"otp:{email}")
    if not saved_otp or otp != saved_otp:
        return jsonify({"error": "Invalid or expired OTP"}), 400
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    user.set_password(new_password)
    db.session.commit()
    r.delete(f"otp:{email}")
    return jsonify({"message": "Password reset successfully"}), 200

@app.route('/api/me', methods=['PUT'])
@token_required
def update_me(current_user):
    """ MỚI: API để cập nhật tên người dùng """
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'message': 'Thiếu tên (name)'}), 400
    
    name = data.get('name').strip()
    if not name:
        return jsonify({'message': 'Tên không được để trống'}), 400
        
    current_user.name = name
    db.session.commit()
     
    return jsonify({
        'message': 'Cập nhật thông tin thành công',
        'user': {
            'id': current_user.id,
            'name': current_user.name,
            'email': current_user.email
        }
    }), 200
# ==========================================================
# 📄 DOCUMENT APIs
# ==========================================================
@app.route('/api/documents', methods=['POST'])
@token_required
def create_document(current_user):
    data = request.get_json()
    filename, file_path = data.get('filename'), data.get('file_path')
    if not filename or not file_path:
        return jsonify({'message': 'Thiếu thông tin'}), 400

    relative_path = os.path.relpath(file_path, start=app.config['UPLOAD_FOLDER'])
    doc = Document(
        filename=filename,
        file_path=relative_path,
        description=data.get('description'),
        visibility=data.get('visibility', 'private'),
        user_id=current_user.id
    )
    tags = data.get('tags', [])
    for t in tags:
        tag = Tag.query.filter_by(name=t.strip().lower()).first() or Tag(name=t.strip().lower())
        db.session.add(tag)
        doc.tags.append(tag)
    db.session.add(doc)
    db.session.commit()
    print(f"[Flask] ✅ Metadata saved for {filename}")
    return jsonify({'message': 'Tạo metadata thành công', 'document_id': doc.id}), 201

@app.route('/api/documents', methods=['GET'])
@token_required
def list_documents(current_user):
    user_docs_only = request.args.get('user') == 'true'

    if user_docs_only:
        query = Document.query.filter_by(
            user_id=current_user.id,
            status='uploaded'
        )
    else:
        from sqlalchemy import or_
        query = Document.query.filter(
            or_(
                Document.user_id == current_user.id,
                Document.visibility == 'public'
            ),
            Document.status == 'uploaded'
        )

    docs = [{
        'id': d.id,
        'filename': d.filename,
        'visibility': d.visibility,
        'user_id': d.user_id
    } for d in query.all()]
    return jsonify({'documents': docs}), 200

@app.route('/api/documents/public', methods=['GET'])
def list_public_documents():
    docs = Document.query.filter_by(visibility='public', status='uploaded').all()
    return jsonify({
        'documents': [
            {
                'id': d.id,
                'filename': d.filename,
                'description': d.description,
                'file_path': d.file_path,
                'tags': [t.name for t in d.tags]
            } for d in docs
        ]
    }), 200

@app.route('/api/documents/<int:doc_id>/download', methods=['GET'])
@token_required
def download(current_user, doc_id):
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'message': 'Không tìm thấy tài liệu'}), 404
    if doc.user_id != current_user.id and doc.visibility == 'private':
        return jsonify({'message': 'Không có quyền truy cập'}), 403
    record_view(current_user, doc)
    directory = os.path.join(app.config['UPLOAD_FOLDER'], os.path.dirname(doc.file_path))
    filename = os.path.basename(doc.file_path)
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/api/documents/<int:doc_id>/trash', methods=['POST'])
@token_required
def trash_document(current_user, doc_id):
    """ Sửa: Chuyển file vào thùng rác (thay vì xóa) """
    doc = Document.query.get(doc_id)
    if not doc or doc.user_id != current_user.id:
        return jsonify({'message': 'Không có quyền xóa'}), 403

    doc.status = 'trashed'  
    db.session.commit()
    return jsonify({'message': 'Đã chuyển vào thùng rác'}), 200

@app.route('/api/documents/<int:doc_id>/restore', methods=['POST'])
@token_required
def restore_document(current_user, doc_id):
    """ Mới: Khôi phục file từ thùng rác """
    doc = Document.query.get(doc_id)
    if not doc or doc.user_id != current_user.id:
        return jsonify({'message': 'Không có quyền'}), 403

    doc.status = 'uploaded'
    db.session.commit()
    return jsonify({'message': 'Khôi phục thành công'}), 200

@app.route('/api/documents/<int:doc_id>/permanent', methods=['DELETE'])
@token_required
def permanent_delete_document(current_user, doc_id):
    """ Mới: Xóa vĩnh viễn (logic của hàm delete cũ) """
    doc = Document.query.get(doc_id)
    if not doc or doc.user_id != current_user.id:
        return jsonify({'message': 'Không có quyền xóa vĩnh viễn'}), 403
 
    abs_path = os.path.join(app.config['UPLOAD_FOLDER'], doc.file_path)
    if os.path.exists(abs_path):
        try: 
            full_dir_path = os.path.dirname(abs_path)
            os.remove(abs_path)
            if not os.listdir(full_dir_path): 
                os.rmdir(full_dir_path)
            print(f"[Flask] 🗑️ File/Folder deleted: {full_dir_path}")
        except Exception as e:
            print(f"Lỗi xóa file vật lý: {e}") 
    UserFavorite.query.filter_by(document_id=doc.id).delete() 
    UserDocumentView.query.filter_by(document_id=doc.id).delete() 
    doc.tags.clear() 
    db.session.flush()  
    db.session.delete(doc)
    db.session.commit()
    return jsonify({'message': 'Xóa tài liệu vĩnh viễn thành công'}), 200
# ==========================================================
# 🚀 SOCKET TRIGGER
# ==========================================================
@app.route('/api/upload/trigger', methods=['POST'])
@token_required
def trigger_upload(current_user):
    socket_url = os.environ.get('SOCKET_SERVER_URL', 'ws://127.0.0.1:6000')
    return jsonify({
        'message': 'Sẵn sàng upload',
        'socket_url': socket_url
    }), 200

# ==========================================================
# 📄 DOCUMENT APIs (BỔ SUNG PHẦN THIẾU)
# ==========================================================

@app.route('/api/documents/<int:doc_id>', methods=['GET'])
@token_required
def get_document_detail(current_user, doc_id):
    """ API để xem chi tiết 1 file (dùng cho modal xem trước) """
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'message': 'Không tìm thấy tài liệu'}), 404
    
    # Kiểm tra quyền: Hoặc là chủ file, hoặc file là public
    if doc.user_id != current_user.id and doc.visibility == 'private':
        return jsonify({'message': 'Không có quyền truy cập'}), 403
    record_view(current_user, doc)
    return jsonify({
        'id': doc.id,
        'filename': doc.filename,
        'file_path': doc.file_path,
        'visibility': doc.visibility,
        'description': doc.description,
        'created_at': doc.created_at,
        'tags': [t.name for t in doc.tags],
        'owner_name': doc.owner.name 
    }), 200


@app.route('/api/documents/<int:doc_id>', methods=['PUT'])
@token_required
def update_document(current_user, doc_id):
    """ API để cập nhật metadata (dùng cho modal chỉnh sửa) """
    doc = Document.query.get(doc_id)
    
    if not doc:
        return jsonify({'message': 'Không tìm thấy tài liệu'}), 404
    
    # Chỉ chủ sở hữu mới được sửa
    if doc.user_id != current_user.id:
        return jsonify({'message': 'Không có quyền chỉnh sửa'}), 403

    data = request.get_json()
    
    # Cập nhật các trường
    if 'description' in data:
        doc.description = data['description']
    if 'visibility' in data:
        doc.visibility = data['visibility']
    
    # Xử lý tags
    if 'tags' in data:
        doc.tags.clear() # Xóa tag cũ
        for t in data.get('tags', []):
            tag_name = t.strip().lower()
            if tag_name:
                tag = Tag.query.filter_by(name=tag_name).first() or Tag(name=tag_name)
                db.session.add(tag)
                doc.tags.append(tag)

    db.session.commit()
    return jsonify({'message': 'Cập nhật thành công'}), 200

# ==========================================================
# 🔌 SOCKET-IO BRIDGE (CẦU NỐI)
# ==========================================================

# Lưu trữ các kết nối TCP cho mỗi client trình duyệt
client_tcp_sockets = {}

@socketio.on('connect')
def handle_connect():
    sid = request.sid
    print(f'[SocketIO] ✅ Client {sid} đã kết nối (Trình duyệt).')

    # Tạo một kết nối TCP MỚI đến server.py cho client này
    try:
        sock = py_socket.socket(py_socket.AF_INET, py_socket.SOCK_STREAM)
        sock.connect((TCP_SERVER_HOST, TCP_SERVER_PORT))
        client_tcp_sockets[sid] = sock
        print(f'[SocketIO] 🔗 Đã tạo cầu nối TCP tới cổng 6000 cho {sid}.')

        # Bắt đầu một luồng riêng để lắng nghe phản hồi từ server.py
        threading.Thread(target=tcp_response_listener, args=(sid, sock), daemon=True).start()
    except Exception as e:
        print(f'[SocketIO] ❌ Không thể kết nối tới server TCP (cổng 6000): {e}')
        socketio.emit('server_error', {'reason': 'Cannot connect to TCP server'}, room=sid)

def tcp_response_listener(sid, tcp_sock):
    """ Lắng nghe phản hồi từ server.py (TCP) và gửi về trình duyệt """
    buffer = b""
    try:
        while True:
            data = tcp_sock.recv(1024)
            if not data:
                break # Server TCP đã đóng

            buffer += data
            # Server TCP gửi tin nhắn JSON bằng \n
            while b'\n' in buffer:
                message_raw, buffer = buffer.split(b'\n', 1)
                try:
                    message_json = json.loads(message_raw.decode('utf-8'))
                    # Gửi phản hồi về đúng trình duyệt
                    socketio.emit('tcp_response', message_json, room=sid)
                except Exception:
                    print(f'[SocketIO] Lỗi parse JSON từ TCP: {message_raw}')

    except Exception as e:
        print(f'[SocketIO] Lỗi luồng TCP listener: {e}')

    # Dọn dẹp khi kết nối hỏng
    if sid in client_tcp_sockets:
        del client_tcp_sockets[sid]
    print(f'[SocketIO] ❎ Đã đóng luồng listener cho {sid}.')


@socketio.on('tcp_message')
def handle_tcp_message(message):
    """ Nhận tin nhắn từ trình duyệt và chuyển tiếp đến server.py (TCP) """
    sid = request.sid
    if sid not in client_tcp_sockets:
        return # Lỗi, client chưa kết nối

    tcp_sock = client_tcp_sockets[sid]

    try:
        if isinstance(message, dict): # Gửi JSON (header)
            tcp_sock.sendall((json.dumps(message) + "\n").encode('utf-8'))
        elif isinstance(message, bytes): # Gửi Bytes (chunk)
            tcp_sock.sendall(message)
    except Exception as e:
        print(f'[SocketIO] Lỗi khi gửi dữ liệu tới TCP: {e}')

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in client_tcp_sockets:
        # Đóng kết nối TCP khi trình duyệt ngắt kết nối
        try:
            client_tcp_sockets[sid].close()
        except Exception: pass
        del client_tcp_sockets[sid]
    print(f'[SocketIO] ❎ Client {sid} đã ngắt kết nối (Trình duyệt).')
@app.route('/api/documents/recent-public', methods=['GET'])
def get_recent_public_documents():
    """
    API cho trang chủ: Lấy 2 tài liệu public mới nhất.
    Không cần token.
    """
    try:
        # Sắp xếp theo ngày tạo, mới nhất trước
        # Lọc chỉ 'public'
        # Lấy 2 kết quả
        recent_docs = Document.query.filter_by(visibility='public') \
                                    .order_by(Document.created_at.desc()) \
                                    .limit(2).all()
        
        docs_list = [{
            'id': d.id,
            'filename': d.filename,
            # Lấy tên người đăng
            'owner_name': d.owner.name, 
            # Định dạng ngày cho dễ đọc
            'created_at': d.created_at.strftime('%d/%m/%Y') 
        } for d in recent_docs]
        
        return jsonify({'documents': docs_list}), 200
    
    except Exception as e:
        print(f"Lỗi /api/documents/recent-public: {e}")
        return jsonify({'message': 'Lỗi máy chủ khi lấy tài liệu'}), 500
# ==========================================================
# 📄 API (Vừa xem, Yêu thích, Thùng rác)
# ==========================================================

@app.route('/api/documents/recently-viewed', methods=['GET'])
@token_required
def get_recently_viewed(current_user): 
    try: 
        docs = Document.query \
            .join(UserDocumentView, Document.id == UserDocumentView.document_id) \
            .filter(UserDocumentView.user_id == current_user.id) \
            .order_by(UserDocumentView.last_viewed_at.desc()) \
            .limit(2).all()
        
        docs_list = [{
            'id': d.id,
            'filename': d.filename,
            'owner_name': d.owner.name, 
            'created_at': d.created_at.strftime('%d/%m/%Y') 
        } for d in docs]
        
        return jsonify({'documents': docs_list}), 200
    except Exception as e:
        print(f"Lỗi /api/documents/recently-viewed: {e}")
        return jsonify({'message': 'Lỗi máy chủ'}), 500

@app.route('/api/documents/trash', methods=['GET'])
@token_required
def get_trash(current_user):
    """ MỚI: Lấy danh sách file trong thùng rác """
    trashed_docs = Document.query.filter_by(
        user_id=current_user.id, 
        status='trashed'
    ).order_by(Document.updated_at.desc()).all()
    
    docs_list = [{ 'id': d.id, 'filename': d.filename } for d in trashed_docs]
    return jsonify({'documents': docs_list}), 200

@app.route('/api/documents/favorites', methods=['GET'])
@token_required
def get_favorites(current_user):
    """ MỚI: Lấy danh sách file yêu thích """
    fav_docs = Document.query \
        .join(UserFavorite, Document.id == UserFavorite.document_id) \
        .filter(UserFavorite.user_id == current_user.id) \
        .order_by(UserFavorite.created_at.desc()).all()

    docs_list = [{
        'id': d.id,
        'filename': d.filename,
        'owner_name': d.owner.name,
        'description': d.description
    } for d in fav_docs]
    
    return jsonify({'documents': docs_list}), 200

@app.route('/api/documents/<int:doc_id>/favorite', methods=['POST'])
@token_required
def toggle_favorite(current_user, doc_id):
    """ MỚI: Bật/Tắt yêu thích (toggle) """
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'message': 'Không tìm thấy tài liệu'}), 404

    fav = UserFavorite.query.filter_by(
        user_id=current_user.id, 
        document_id=doc.id
    ).first()
    
    if fav: 
        db.session.delete(fav)
        db.session.commit()
        return jsonify({'message': 'Đã bỏ yêu thích', 'isFavorited': False}), 200
    else: 
        new_fav = UserFavorite(user_id=current_user.id, document_id=doc.id)
        db.session.add(new_fav)
        db.session.commit()
        return jsonify({'message': 'Đã yêu thích', 'isFavorited': True}), 201
@app.route('/api/documents/search', methods=['GET'])
@token_required
def search_documents(current_user): 
    keyword = request.args.get('q', '').strip()
    if not keyword:
        return jsonify({'message': 'Vui lòng nhập từ khóa tìm kiếm'}), 400
 
    docs_query = Document.query \
        .outerjoin(document_tags) \
        .outerjoin(Tag) \
        .filter(
            Document.status == 'uploaded',
            or_(
                Document.filename.ilike(f'%{keyword}%'),
                Document.description.ilike(f'%{keyword}%'),
                Tag.name.ilike(f'%{keyword}%')
            ), 
            or_(
                Document.visibility == 'public',
                Document.user_id == current_user.id
            )
        ).distinct() \
        .order_by(Document.created_at.desc())

    docs = [{
        'id': d.id,
        'filename': d.filename,
        'description': d.description,
        'visibility': d.visibility,
        'user_id': d.user_id,
        'tags': [t.name for t in d.tags],
        'owner_name': d.owner.name
    } for d in docs_query.all()]

    if not docs:
        return jsonify({'message': 'Không tìm thấy tài liệu nào', 'documents': []}), 200

    return jsonify({'documents': docs}), 200
# ==========================================================
# 🏁 MAIN ENTRY 
# ==========================================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print("🚀 Khởi chạy Flask (API) và SocketIO (Cầu nối) trên cổng 5000...")
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)