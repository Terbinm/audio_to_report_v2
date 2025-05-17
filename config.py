#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Flask 應用配置文件
"""
import os
from pathlib import Path

# 基本配置
SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
DEBUG = True

# 資料庫配置
SQLALCHEMY_DATABASE_URI = 'sqlite:///audio_to_report.db'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# 檔案上傳配置
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'flac', 'm4a'}
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB 上傳限制

# 輸出目錄配置
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')
TRANSCRIPT_FOLDER = os.path.join(OUTPUT_FOLDER, 'transcripts')
VISUALIZATION_FOLDER = os.path.join(OUTPUT_FOLDER, 'visualizations')
REPORT_FOLDER = os.path.join(OUTPUT_FOLDER, 'reports')

# 複製一份可視化圖表到靜態目錄以便網頁顯示
STATIC_OUTPUT_FOLDER = os.path.join(BASE_DIR, 'static', 'outputs')
STATIC_VISUALIZATION_FOLDER = os.path.join(STATIC_OUTPUT_FOLDER, 'visualizations')


####################預設配置######################
# 音訊轉錄配置
DEFAULT_WHISPER_MODEL = "large"  # 可選: tiny, base, small, medium, large
DEFAULT_LANGUAGE = "zh"  # 語言代碼 (例如: zh, en)，若為 None 則自動檢測
DEVICE = "cuda"  # 計算設備 (cpu 或 cuda)，若為 None 則自動選擇

# 說話者分割選項(預設)
DEFAULT_SPEAKERS_COUNT = None  # 固定的說話者數量，例如: 2
DEFAULT_SPEAKER_MIN = 2  # 最小說話者數量
DEFAULT_SPEAKER_MAX = 10  # 最大說話者數量
DEFAULT_VISUALIZE = True  # 是否生成說話者分割的可視化圖表

# HuggingFace token 用於下載分割模型
# 可以通過環境變數設定
DEFAULT_HF_TOKEN = "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"

# Ollama LLM 配置
DEFAULT_OLLAMA_HOST = "192.168.1.14"  # Ollama 主機地址
DEFAULT_OLLAMA_PORT = "11434"  # Ollama 端口
DEFAULT_OLLAMA_MODEL = "phi4:14b"  # 預設模型

# 系統提示詞（用於 LLM 生成報告）
DEFAULT_SYSTEM_PROMPT = """
你是一個專業的會議紀錄助手。你的任務是根據會議逐字稿生成一份結構良好的會議紀錄。

請按照以下格式生成報告：
1. 會議標題：基於逐字稿內容推斷一個合適的標題
2. 會議時間：根據逐字稿提供的時間資訊
3. 與會人員：列出所有在逐字稿中發言的人員
4. 會議內容摘要：簡潔概述會議的主要內容和目的
5. 討論要點：列出會議中討論的主要議題和決定
6. 行動項目：列出會議中提到的需要執行的任務，包括負責人和時間
7. 結論：總結會議的結果和下一步計劃

請使用markdown格式，使報告易於閱讀。報告應該清晰、專業，並忠實反映逐字稿中的重要信息。
"""
