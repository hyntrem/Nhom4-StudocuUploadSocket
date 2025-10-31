import os
import jwt
import datetime
from functools import wraps
from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from dotenv import load_dotenv
import secrets
import string
import smtplib
from email.mime.text import MIMEText
import redis
from flask import send_from_directory

# Tải biến môi trường (tạo file .env)
load_dotenv()

app = Flask(__name__)
CORS(app) # Cho phép tất cả các domain gọi API này

# --- CẤU HÌNH ---
# Lấy key bí mật từ file .env
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secretkey')
# Cấu hình CSDL (xampp)
# Đảm bảo đã tạo CSDL 'studocu_db'
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASS = os.environ.get('DB_PASS', '')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'upload_file')
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}'

# Lấy SENDER_EMAIL và APP_PASSWORD từ biến môi trường (.env)
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'lelonh0810')
APP_PASSWORD = os.environ.get('APP_PASSWORD', 'fyrszjrttsnlybpd')
# Cấu hình Redis
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

# Khởi tạo các extension
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

try:
    # decode_responses=True để tự động chuyển bytes sang string
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()
    print("Kết nối Redis thành công!")
except redis.exceptions.ConnectionError as e:
    print(f"LỖI: không thể kết nối Redis. {e}")
    r = None # Đặt là None để code bên dưới không bị lỗi


# --- MODELS (Định nghĩa cấu trúc bảng CSDL) ---
# Bảng trung gian cho quan hệ nhiều-nhiều
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
        """Tạo hash mật khẩu từ mật khẩu thô."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Kiểm tra mật khẩu thô có khớp với hash không."""
        return bcrypt.check_password_hash(self.password_hash, password)

class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False) # Socket server sẽ lưu file vào đây
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

# --- DECORATOR (Hàm kiểm tra JWT) ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            # Lấy token từ header: "Bearer <token>"
            token = request.headers['Authorization'].split(" ")[1]

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try: 
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id']) 
            if not current_user:
                 return jsonify({'message': 'User not found!'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid!'}), 401

        return f(current_user, *args, **kwargs) # Truyền user đã xác thực vào hàm API
    return decorated


# === PHẦN 1: USER & AUTHENTICATION ===

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({'message': 'Vui lòng nhập đủ thông tin'}), 400

    # Kiểm tra email đã tồn tại chưa
    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Email đã tồn tại'}), 409 # 409 Conflict

    # Băm mật khẩu
    new_user = User(name=name, email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'message': 'Đăng ký thành công!'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'message': 'Vui lòng nhập đủ thông tin'}), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({'message': 'Email không tồn tại'}), 404

    # Kiểm tra mật khẩu
    if user.check_password(password):
        # Tạo JWT
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24) # Hết hạn sau 24h
        }, app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({
            'message': 'Đăng nhập thành công', 
            'token': token,
            'user': { 'name': user.name, 'email': user.email }
        }), 200
    
    return jsonify({'message': 'Sai mật khẩu'}), 401

@app.route('/api/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not old_password or not new_password:
        return jsonify({'message': 'Thiếu thông tin'}), 400
    
    if not current_user.check_password(old_password):
        return jsonify({'message': 'Mật khẩu cũ không đúng'}), 400

    current_user.set_password(new_password)
    db.session.commit()
    return jsonify({'message': 'Đổi mật khẩu thành công'}), 200

# (Tùy chọn) API lấy thông tin user hiện tại (để kiểm tra token)
@app.route('/api/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    return jsonify({
        'id': current_user.id,
        'name': current_user.name,
        'email': current_user.email
    }), 200

@app.route("/send-otp", methods=["POST"])
def send_otp():
    """
    Gửi mã OTP đến email của người dùng để đặt lại mật khẩu.
    """
    if not r:
        return jsonify({"error": "Dịch vụ Redis không khả dụng."}), 503
    email = request.json.get("email")
    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "Email does not exist"}), 404

    # Tạo OTP ngẫu nhiên 6 chữ số
    otp = ''.join(secrets.choice(string.digits) for _ in range(6))
    r.setex(f"otp:{email}", 300, otp)  # Lưu OTP 5 phút

    # Gửi email OTP
    try:
        subject = "Your OTP Code"
        body = f"Your OTP code is: {otp}. It will expire in 5 minutes."
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, email, msg.as_string())

        return jsonify({"message": "OTP has been sent to your email."}), 200

    except Exception as e:
        print(f"ERROR sending email: {e}")
        return jsonify({"error": "Failed to send OTP email."}), 500


# ===============================
# XÁC THỰC OTP & ĐẶT LẠI MẬT KHẨU
# ===============================
@app.route("/reset-password", methods=["POST"])
def reset_password():
    """
    Kiểm tra OTP và đặt lại mật khẩu mới.
    """
    if not r:
        return jsonify({"error": "Dịch vụ Redis không khả dụng."}), 503
    data = request.get_json()
    if not data or not all(k in data for k in ["email", "otp", "new_password"]):
        return jsonify({"error": "Missing required fields: email, otp, new_password"}), 400

    email = data["email"]
    input_otp = data["otp"]
    new_password = data["new_password"]

    saved_otp = r.get(f"otp:{email}")
    if not saved_otp:
        return jsonify({"error": "OTP expired or not found"}), 400

    if input_otp != saved_otp:
        return jsonify({"error": "Invalid OTP"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Cập nhật mật khẩu
    user.set_password(new_password)
    db.session.commit()
    r.delete(f"otp:{email}")

    return jsonify({"message": "Password has been reset successfully."}), 200


# === PHẦN 2: QUẢN LÝ TÀI LIỆU ===

@app.route('/api/documents', methods=['POST'])
@token_required
def create_document_metadata(current_user):
    """
    API này được gọi SAU KHI file đã được upload lên socket server.
    Frontend (hoặc socket server) sẽ gọi API này để lưu metadata.
    """
    data = request.get_json()
    filename = data.get('filename')
    file_path = data.get('file_path') # Đường dẫn mà socket server đã lưu file
    description = data.get('description')
    visibility = data.get('visibility', 'private')
    tags_data = data.get('tags', [])

    if not filename or not file_path:
        return jsonify({'message': 'Thiếu thông tin file'}), 400

    new_doc = Document(
        filename=filename,
        file_path=file_path,
        description=description,
        visibility=visibility,
        user_id=current_user.id
    )
    if isinstance(tags_data, list):
        for tag_name in tags_data:
            tag_name_clean = tag_name.strip().lower()
            if tag_name_clean:
                # Kiểm tra xem tag đã tồn tại chưa
                tag = Tag.query.filter_by(name=tag_name_clean).first()
                if not tag:
                    # Nếu chưa, tạo tag mới
                    tag = Tag(name=tag_name_clean)
                    db.session.add(tag)
                # Thêm tag vào tài liệu
                new_doc.tags.append(tag)
    db.session.add(new_doc)
    db.session.commit()
    
    return jsonify({'message': 'Tạo metadata thành công', 'document_id': new_doc.id}), 201


@app.route('/api/documents', methods=['GET'])
@token_required
def get_documents(current_user):
    """
    Lấy danh sách tài liệu.
    Filter theo: user, public/private
    """
    visibility = request.args.get('visibility')
    only_mine = request.args.get('user', 'false').lower() == 'true'

    query = Document.query
    
    tag_name = request.args.get('tag')
    if tag_name:
        # Join với bảng tags và lọc
        query = query.join(Document.tags).filter(Tag.name == tag_name.lower())
    
    if only_mine:
        query = query.filter_by(user_id=current_user.id)
    else:
        # Lấy file của mình HOẶC file public
        query = query.filter(
            (Document.user_id == current_user.id) | (Document.visibility == 'public')
        )

    if visibility in ['public', 'private']:
        query = query.filter_by(visibility=visibility)

    documents = query.all()
    output = []
    for doc in documents:
        output.append({
            'id': doc.id,
            'filename': doc.filename,
            'description': doc.description,
            'visibility': doc.visibility,
            'created_at': doc.created_at,
            'owner_id': doc.user_id,
            'tags': [tag.name for tag in doc.tags]
        })
    
    return jsonify({'documents': output}), 200


@app.route('/api/documents/<int:doc_id>', methods=['GET'])
@token_required
def get_document_detail(current_user, doc_id):
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'message': 'Không tìm thấy tài liệu'}), 404

    # Kiểm tra quyền: là chủ sở hữu HOẶC tài liệu là public
    if doc.user_id != current_user.id and doc.visibility == 'private':
        return jsonify({'message': 'Không có quyền truy cập'}), 403

    return jsonify({
        'id': doc.id,
        'filename': doc.filename,
        'file_path': doc.file_path, # Chỉ trả về nếu là chủ sở hữu?
        'description': doc.description,
        'visibility': doc.visibility,
        'created_at': doc.created_at,
        'owner_id': doc.user_id,
        'tags': [tag.name for tag in doc.tags]
    }), 200

@app.route('/api/documents/<int:doc_id>', methods=['PUT'])
@token_required
def update_document(current_user, doc_id):
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'message': 'Không tìm thấy tài liệu'}), 404
    
    # Chỉ chủ sở hữu mới được sửa
    if doc.user_id != current_user.id:
        return jsonify({'message': 'Không có quyền sửa'}), 403

    data = request.get_json()
    doc.description = data.get('description', doc.description)
    doc.visibility = data.get('visibility', doc.visibility)
    # Cập nhật tags...
    if 'tags' in data and isinstance(data['tags'], list):
        doc.tags.clear() # Xóa hết tag cũ
        tags_data = data.get('tags', [])
        for tag_name in tags_data:
            tag_name_clean = tag_name.strip().lower()
            if tag_name_clean:
                tag = Tag.query.filter_by(name=tag_name_clean).first()
                if not tag:
                    tag = Tag(name=tag_name_clean)
                    db.session.add(tag)
                doc.tags.append(tag)
    
    db.session.commit()
    return jsonify({'message': 'Cập nhật thành công'}), 200

@app.route('/api/documents/<int:doc_id>', methods=['DELETE'])
@token_required
def delete_document(current_user, doc_id):
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'message': 'Không tìm thấy tài liệu'}), 404
    
    # Chỉ chủ sở hữu mới được xóa
    if doc.user_id != current_user.id:
        return jsonify({'message': 'Không có quyền xóa'}), 403

    # TODO: Cần xóa file vật lý trên server (do socket server quản lý)
    # ...

    db.session.delete(doc)
    db.session.commit()
    return jsonify({'message': 'Xóa tài liệu thành công'}), 200

@app.route('/api/documents/<int:doc_id>/download', methods=['GET'])
@token_required
def download_file(current_user, doc_id):
    """
    API để download file.
    """
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'message': 'Không tìm thấy tài liệu'}), 404

    # Kiểm tra quyền: là chủ sở hữu HOẶC tài liệu là public
    if doc.user_id != current_user.id and doc.visibility == 'private':
        return jsonify({'message': 'Không có quyền truy cập'}), 403

    try:
        # file_path trong DB phải là đường dẫn TƯƠNG ĐỐI
        # Ví dụ: "user_15/ten_file.pdf"
        # Thư mục UPLOAD_FOLDER là: ".../backend_api/uploads"
        
        # Tách đường dẫn thành thư mục và tên file
        directory = os.path.dirname(doc.file_path)
        filename = os.path.basename(doc.file_path)
        
        # Gửi file từ: ".../backend_api/uploads/user_15/ten_file.pdf"
        return send_from_directory(
            os.path.join(app.config['UPLOAD_FOLDER'], directory),
            filename,
            as_attachment=True # Báo trình duyệt tải file về (thay vì hiển thị)
        )
    except FileNotFoundError:
        return jsonify({'message': 'Lỗi: Không tìm thấy file trên server'}), 404
    except Exception as e:
        print(f"Lỗi download file: {e}")
        return jsonify({'message': 'Lỗi server khi xử lý file'}), 500

# ===============================
# API TRIGGER UPLOAD (Lấy địa chỉ Socket)
# ===============================
@app.route('/api/upload/trigger', methods=['POST'])
@token_required
def trigger_upload(current_user):
    """
    API này được gọi TRƯỚC KHI upload.
    Client (frontend) gọi API này để lấy địa chỉ Socket Server.
    """
    # Lấy địa chỉ socket từ file .env
    socket_url = os.environ.get('SOCKET_SERVER_URL', 'ws://127.0.0.1:6000') 

    # (Tùy chọn) Bạn có thể kiểm tra quota upload của user ở đây
    # if current_user.upload_count > 100:
    #    return jsonify({'message': 'Đã hết dung lượng upload'}), 403

    return jsonify({
        'message': 'Sẵn sàng upload. Hãy kết nối tới socket.',
        'socket_url': socket_url
    }), 200

# --- Khởi chạy server ---
if __name__ == '__main__':
    # Tạo bảng nếu chưa tồn tại
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000) # Backend chạy ở cổng 5000