"""
處理登入和註冊頁面的 routes
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from models.user import User
from extensions import db
import datetime

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
        flash('請檢查您的登入資訊並重試。', 'danger')
        return redirect(url_for('auth.login'))

    # 更新最後登入時間
    user.last_login = datetime.datetime.now()
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
        flash('電子郵件地址已被註冊。', 'danger')
        return redirect(url_for('auth.register'))

    # 創建新用戶
    new_user = User(
        email=email,
        name=name,
        password=generate_password_hash(password, method='pbkdf2:sha256')
    )

    # 添加用戶到數據庫
    db.session.add(new_user)
    db.session.commit()

    # 重定向到登入頁面
    flash('註冊成功，請登入。', 'success')
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
    # 這裡將來會顯示用戶的音訊檔案和報告
    from models.db_models import AudioFile, Transcript, Report

    # 獲取最新的5個音訊檔案
    audio_files = AudioFile.query.filter_by(user_id=current_user.id).order_by(AudioFile.created_at.desc()).limit(5).all()

    # 獲取用戶的所有轉錄記錄
    transcripts = Transcript.query.join(AudioFile).filter(AudioFile.user_id == current_user.id).all()

    # 獲取最新的5個報告
    reports = Report.query.filter_by(user_id=current_user.id).order_by(Report.created_at.desc()).limit(5).all()

    return render_template('dashboard.html',
                          name=current_user.name,
                          audio_files=audio_files,
                          transcripts=transcripts,
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

    flash('個人資料已更新。', 'success')
    return redirect(url_for('auth.profile'))


@auth.route('/change_password', methods=['POST'])
@login_required
def change_password():
    """變更用戶密碼"""
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    # 檢查新密碼是否匹配
    if new_password != confirm_password:
        flash('新密碼與確認密碼不匹配', 'danger')
        return redirect(url_for('auth.profile'))

    # 檢查新密碼長度
    if len(new_password) < 6:
        flash('新密碼長度必須至少 6 個字元', 'danger')
        return redirect(url_for('auth.profile'))

    # 檢查當前密碼是否正確
    if not check_password_hash(current_user.password, current_password):
        flash('當前密碼不正確', 'danger')
        return redirect(url_for('auth.profile'))

    # 更新密碼
    current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
    db.session.commit()

    flash('密碼已成功更新', 'success')
    return redirect(url_for('auth.profile'))