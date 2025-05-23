"""
Flask 應用入口點
初始化 Flask 應用，設定藍圖 (Blueprints)，配置基本設定
"""
from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
import os
from pathlib import Path
import datetime

# 從共享模組導入 db 和 migrate
from extensions import db, migrate


def create_app(test_config=None):
    """建立並配置 Flask 應用"""
    # 建立 Flask 應用
    app = Flask(__name__, instance_relative_config=True)

    # 載入基本配置
    app.config.from_object('config')

    # 如果有測試配置，則覆蓋基本配置
    if test_config is not None:
        app.config.from_mapping(test_config)

    # 確保實例文件夾存在
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    # 確保上傳和輸出目錄存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['TRANSCRIPT_FOLDER'], exist_ok=True)
    os.makedirs(app.config['VISUALIZATION_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)
    os.makedirs(app.config['STATIC_VISUALIZATION_FOLDER'], exist_ok=True)

    # 初始化數據庫
    db.init_app(app)
    migrate.init_app(app, db)

    # 設定登入管理器
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    # 從模型中引入 User 類並設定用戶加載函數
    from models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # 註冊藍圖
    # 註冊認證藍圖
    from auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    # 註冊音訊和報告藍圖
    from routes.audio_routes import audio as audio_blueprint
    from routes.report_routes import report as report_blueprint
    app.register_blueprint(audio_blueprint)
    app.register_blueprint(report_blueprint)

    # 主頁路由重定向到儀表板
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('auth.dashboard'))
        return redirect(url_for('auth.login'))

    # 錯誤處理
    @app.errorhandler(404)
    def page_not_found(e):
        return "頁面未找到", 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return "服務器內部錯誤", 500

    # 為所有模板添加全局變數
    @app.context_processor
    def inject_globals():
        return {
            'now': datetime.datetime.now()
        }

    # 添加自定義過濾器
    @app.template_filter('filesizeformat')
    def filesizeformat_filter(value):
        """將檔案大小轉換為可讀格式"""
        if not isinstance(value, (int, float)):
            return value

        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(value)
        unit_index = 0

        while size >= 1024.0 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1

        return f"{size:.1f} {units[unit_index]}"

    # 添加 markdown 過濾器
    @app.template_filter('markdown')
    def markdown_filter(text):
        """轉換 Markdown 為 HTML"""
        try:
            import markdown
            return markdown.markdown(text)
        except ImportError:
            return text

    # 創建數據庫表格
    with app.app_context():
        db.create_all()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)