"""
共享資源模組，用於避免循環導入問題
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# 創建共享的 SQLAlchemy 實例
db = SQLAlchemy()
migrate = Migrate()