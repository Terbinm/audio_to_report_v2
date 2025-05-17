"""
用戶模型
定義用戶相關的數據庫模型
"""
from flask_login import UserMixin
from datetime import datetime
from extensions import db

class User(UserMixin, db.Model):
    """用戶模型，用於認證和用戶管理"""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # 關聯到用戶的音訊檔案 (一對多關係)
    audio_files = db.relationship('AudioFile', backref='user', lazy=True, cascade="all, delete-orphan")

    # 用戶的歷史生成記錄 (一對多關係)
    reports = db.relationship('Report', backref='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.email}>'