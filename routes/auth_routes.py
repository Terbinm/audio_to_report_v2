"""
認證相關路由
處理登入、註冊、登出等基本認證功能
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from models.user import User
from app import db

# 創建藍圖
auth = Blueprint('auth', __name__)


@auth.route('/login')
def login():
    """登入頁面"""
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    return render_template('auth/login.html')


@auth.route('/login', methods=['POST'])
def login_post():
    """處理登入請求"""
    email = request.form.get('email')
    password = request.form.get('password')
    remember = True if request.form.get('remember') else False

    # 檢查用戶是否存在
    user = User.query.filter_by(email=email).first()

    # 檢查密碼
    if not user or not check_password_hash(user.password, password):
        flash('請檢查您的登入資訊並重試。')
        return redirect(url_for('auth.login'))

    # 更新最後登入時間
    user.last_login = db.func.now()
    db.session.commit()

    # 登入用戶
    login_user(user, remember=remember)
    return redirect(url_for('auth.dashboard'))


@auth.route('/register')
def register():
    """註冊頁面"""
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    return render_template('auth/register.html')


@auth.route('/register', methods=['POST'])
def register_post():
    """處理註冊請求"""
    email = request.form.get('email')
    name = request.form.get('name')
    password = request.form.get('password')

    # 檢查用戶是否已存在
    user = User.query.filter_by(email=email).first()
    if user:
        flash('電子郵件地址已被註冊。')
        return redirect(url_for('auth.register'))

    # 創建新用戶
    new_user = User()

    # new_user = User(
    #     email=email,
    #     name=name,
    #     password=generate_password_hash(password, method='pbkdf2:sha256')
    # )

    # 添加用戶到數據庫
    db.session.add(new_user)
    db.session.commit()

    # 重定向到登入頁面
    flash('註冊成功，請登入。')
    return redirect(url_for('auth.login'))


@auth.route('/logout')
@login_required
def logout():
    """登出用戶"""
    logout_user()
    return redirect(url_for('auth.login'))


@auth.route('/dashboard')
@login_required
def dashboard():
    """用戶儀表板"""
    # 獲取用戶的音訊檔案和報告
    from models.db_models import AudioFile, Report

    audio_files = AudioFile.query.filter_by(user_id=current_user.id).order_by(AudioFile.created_at.desc()).limit(5)
    reports = Report.query.filter_by(user_id=current_user.id).order_by(Report.created_at.desc()).limit(5)

    return render_template('dashboard.html',
                           name=current_user.name,
                           audio_files=audio_files,
                           reports=reports)


@auth.route('/profile')
@login_required
def profile():
    """用戶個人資料"""
    return render_template('auth/profile.html', user=current_user)


@auth.route('/profile', methods=['POST'])
@login_required
def profile_update():
    """更新用戶個人資料"""
    name = request.form.get('name')

    # 更新用戶名稱
    current_user.name = name
    db.session.commit()

    flash('個人資料已更新。')
    return redirect(url_for('auth.profile'))