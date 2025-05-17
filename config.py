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

# 使用者認證相關配置
AUTH_USERS_ENABLED = True  # 是否啟用用戶認證系統
SESSION_LIFETIME = 24  # 會話生命週期 (小時)

# 網站配置
SITE_TITLE = "音訊轉報告系統"
SITE_DESCRIPTION = "將會議音訊轉換為結構化會議報告"

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
REPORT_DEBUG_FOLDER = os.path.join(OUTPUT_FOLDER, 'debug')  # 調試資訊儲存目錄

# 複製一份可視化圖表到靜態目錄以便網頁顯示
STATIC_OUTPUT_FOLDER = os.path.join(BASE_DIR, 'static', 'outputs')
STATIC_VISUALIZATION_FOLDER = os.path.join(STATIC_OUTPUT_FOLDER, 'visualizations')

# 音訊轉錄配置
DEFAULT_WHISPER_MODEL = "large"  # 可選: tiny, base, small, medium, large
DEFAULT_LANGUAGE = "zh"  # 語言代碼 (例如: zh, en)，若為 None 則自動檢測
DEVICE = "cuda"  # 計算設備 (cpu 或 cuda)，若為 None 則自動選擇
PREPROCESS_AUDIO = True  # 是否自動預處理音訊(轉換聲道等)

# 說話者分割選項(預設)
DEFAULT_SPEAKERS_COUNT = None  # 固定的說話者數量，例如: 2
DEFAULT_SPEAKER_MIN = 2  # 最小說話者數量
DEFAULT_SPEAKER_MAX = 10  # 最大說話者數量
DEFAULT_VISUALIZE = True  # 是否生成說話者分割的可視化圖表

# LLM 生成參數配置
DEFAULT_TEMPERATURE = 0.7      # 溫度參數，控制隨機性 (0.0-1.0)，值越低越確定性
DEFAULT_TOP_P = 0.9            # 頂部 P 採樣，控制結果多樣性 (0.0-1.0)
DEFAULT_TOP_K = 40             # 頂部 K 採樣，限制候選詞彙數量
DEFAULT_FREQUENCY_PENALTY = 0.0  # 頻率懲罰，減少重複 (-2.0-2.0)
DEFAULT_PRESENCE_PENALTY = 0.0   # 存在懲罰，減少主題重複 (-2.0-2.0)
DEFAULT_REPEAT_PENALTY = 1.1     # 重複懲罰，專用於減少文字重複
DEFAULT_SEED = None              # 隨機種子，確保結果可重複

# HuggingFace token 用於下載分割模型
# 可以通過環境變數設定
DEFAULT_HF_TOKEN = os.environ.get('HF_TOKEN') or "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"

# Ollama LLM 配置
DEFAULT_OLLAMA_HOST = os.environ.get('OLLAMA_HOST') or "192.168.1.14"  # Ollama 主機地址
DEFAULT_OLLAMA_PORT = os.environ.get('OLLAMA_PORT') or "11434"  # Ollama 端口
DEFAULT_OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL') or "phi4:14b"  # 預設模型

# 報告生成配置
MAX_REPORT_TOKENS = 4000  # 報告生成的最大 token 數量
REPORT_STREAM_CHUNK_SIZE = 50  # 每次從 LLM 獲取的 token 數量
REPORT_FORMATS = ["markdown", "pdf"]  # 支援的報告格式

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

請使用markdown格式，使報告易於閱讀。報告應該清晰、專業，並忠實反映逐字稿中的重要信息。並且必須使用繁體中文回答！
"""