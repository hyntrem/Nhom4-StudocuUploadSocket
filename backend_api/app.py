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
    tags = db.relationship('Tag', secondary=document_tags, lazy='subquery',
                           backref=db.backref('documents', lazy=True))

class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

# ==========================================================
# 🔐 JWT DECORATOR
# ==========================================================
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
    query = Document.query.filter(
        (Document.user_id == current_user.id) | (Document.visibility == 'public')
    )
    docs = [{
        'id': d.id,
        'filename': d.filename,
        'file_path': d.file_path,
        'visibility': d.visibility,
        'description': d.description,
        'created_at': d.created_at,
        'tags': [t.name for t in d.tags]
    } for d in query.all()]
    return jsonify({'documents': docs}), 200


@app.route('/api/documents/<int:doc_id>/download', methods=['GET'])
@token_required
def download(current_user, doc_id):
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'message': 'Không tìm thấy tài liệu'}), 404
    if doc.user_id != current_user.id and doc.visibility == 'private':
        return jsonify({'message': 'Không có quyền truy cập'}), 403
    directory = os.path.join(app.config['UPLOAD_FOLDER'], os.path.dirname(doc.file_path))
    filename = os.path.basename(doc.file_path)
    return send_from_directory(directory, filename, as_attachment=True)


@app.route('/api/documents/<int:doc_id>', methods=['DELETE'])
@token_required
def delete_document(current_user, doc_id):
    doc = Document.query.get(doc_id)
    if not doc or doc.user_id != current_user.id:
        return jsonify({'message': 'Không có quyền xóa'}), 403
    abs_path = os.path.join(app.config['UPLOAD_FOLDER'], doc.file_path)
    if os.path.exists(abs_path):
        os.remove(abs_path)
        print(f"[Flask] 🗑️ File deleted: {abs_path}")
    db.session.delete(doc)
    db.session.commit()
    return jsonify({'message': 'Xóa tài liệu thành công'}), 200

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
# 🏁 MAIN ENTRY
# ==========================================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
