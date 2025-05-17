#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成 audio_to_report 專案資料夾結構的腳本
"""

import os
import sys


def create_directory(path):
    """創建目錄"""
    try:
        os.makedirs(path, exist_ok=True)
        print(f"創建目錄: {path}")
    except Exception as e:
        print(f"無法創建目錄 {path}: {e}")
        sys.exit(1)


def create_file(path, content=""):
    """創建檔案"""
    try:
        # 確保檔案的目錄存在
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # 檢查檔案是否已存在
        if not os.path.exists(path):
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"創建檔案: {path}")
        else:
            print(f"檔案已存在，略過: {path}")
    except Exception as e:
        print(f"無法創建檔案 {path}: {e}")


def main():
    """主函數"""

    # 專案根目錄
    root = "audio_to_report"
    create_directory(root)

    # 定義資料夾結構
    directories = [
        "",  # 根目錄
        "models",
        "processors",
        "routes",
        "static",
        "static/css",
        "static/js",
        "static/images",
        "static/outputs",
        "templates",
        "templates/auth",
        "uploads",
        "outputs",
        "outputs/transcripts",
        "outputs/visualizations",
        "outputs/reports",
        "tests",
        "utils"
    ]

    # 創建所有目錄
    for directory in directories:
        path = os.path.join(root, directory)
        create_directory(path)

    # 定義檔案列表
    files = [
        "app.py",  # 主應用程式 (Flask 應用入口)
        "config.py",  # 配置文件
        "auth.py",  # 使用者認證模組
        "models/__init__.py",
        "models/db_models.py",  # 資料庫模型
        "models/user.py",  # 使用者模型
        "processors/__init__.py",
        "processors/audio_processor.py",  # 音訊處理器
        "processors/report_generator.py",  # 報告生成器
        "routes/__init__.py",
        "routes/auth_routes.py",  # 認證相關路由
        "routes/audio_routes.py",  # 音訊處理相關路由
        "routes/report_routes.py",  # 報告生成相關路由
        "templates/auth/login.html",
        "templates/auth/register.html",
        "templates/dashboard.html",  # 儀表板頁面
        "templates/layout.html",  # 基本版面
        "templates/upload.html",  # 上傳頁面
        "templates/process.html",  # 處理頁面
        "templates/report.html",  # 報告頁面
        "tests/__init__.py",
        "tests/test_audio.py",
        "tests/test_report.py",
        "utils/__init__.py",
        "utils/file_utils.py",  # 檔案處理工具
        "utils/stream_helpers.py",  # 串流處理工具
        "requirements.txt",  # 相依套件
        "README.md"  # 說明文件
    ]

    # 創建所有檔案
    for file in files:
        create_file(os.path.join(root, file))

    print("\n資料夾結構創建完成！")
    print(f"專案路徑: {os.path.abspath(root)}")


if __name__ == "__main__":
    main()