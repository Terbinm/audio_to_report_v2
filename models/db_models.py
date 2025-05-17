"""
資料庫模型
定義系統中所需的各種數據模型
"""
from app import db
from datetime import datetime
import enum


class ProcessingStatus(enum.Enum):
    """處理狀態枚舉"""
    PENDING = "pending"  # 等待處理
    PROCESSING = "processing"  # 處理中
    COMPLETED = "completed"  # 完成
    FAILED = "failed"  # 失敗
    CANCELED = "canceled"  # 取消


class TranscriptStatus(enum.Enum):
    """轉錄狀態枚舉"""
    ORIGINAL = "original"  # 原始轉錄
    EDITED = "edited"  # 已編輯


class ReportStatus(enum.Enum):
    """報告狀態枚舉"""
    GENERATING = "generating"  # 生成中
    COMPLETED = "completed"  # 完成
    FAILED = "failed"  # 失敗
    CANCELED = "canceled"  # 取消


class AudioFile(db.Model):
    """音訊檔案模型"""
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # 檔案大小 (bytes)
    duration = db.Column(db.Float, nullable=True)  # 音訊時長 (秒)

    # 音訊處理設定
    whisper_model = db.Column(db.String(50), nullable=False)
    language = db.Column(db.String(10), nullable=True)
    speakers_count = db.Column(db.Integer, nullable=True)
    speaker_min = db.Column(db.Integer, nullable=True)
    speaker_max = db.Column(db.Integer, nullable=True)

    # 處理狀態
    status = db.Column(db.Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    progress = db.Column(db.Float, default=0)  # 處理進度 (0-100)
    error_message = db.Column(db.Text, nullable=True)  # 若處理失敗，錯誤訊息

    # 時間戳記
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)

    # 關聯
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transcripts = db.relationship('Transcript', backref='audio_file', lazy=True, cascade="all, delete-orphan")
    reports = db.relationship('Report', backref='audio_file', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<AudioFile {self.original_filename}>'


class Transcript(db.Model):
    """轉錄結果模型"""
    id = db.Column(db.Integer, primary_key=True)

    # 轉錄檔案路徑
    csv_path = db.Column(db.String(255), nullable=True)
    txt_path = db.Column(db.String(255), nullable=True)
    visualization_path = db.Column(db.String(255), nullable=True)

    # 轉錄內容摘要
    total_duration = db.Column(db.Float, nullable=True)  # 總時長 (秒)
    speakers_count = db.Column(db.Integer, nullable=True)  # 識別出的說話者數量
    word_count = db.Column(db.Integer, nullable=True)  # 字數統計

    # 狀態
    status = db.Column(db.Enum(TranscriptStatus), default=TranscriptStatus.ORIGINAL)

    # 時間戳記
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 關聯
    audio_file_id = db.Column(db.Integer, db.ForeignKey('audio_file.id'), nullable=False)

    def __repr__(self):
        return f'<Transcript for AudioFile {self.audio_file_id}>'


class Report(db.Model):
    """報告模型"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=True)

    # 報告設定
    system_prompt = db.Column(db.Text, nullable=False)  # 用於生成報告的系統提示詞
    ollama_model = db.Column(db.String(50), nullable=False)  # 使用的 LLM 模型

    # 報告檔案路徑
    markdown_path = db.Column(db.String(255), nullable=True)
    pdf_path = db.Column(db.String(255), nullable=True)

    # 狀態
    status = db.Column(db.Enum(ReportStatus), default=ReportStatus.GENERATING)
    progress = db.Column(db.Float, default=0)  # 生成進度 (0-100)
    error_message = db.Column(db.Text, nullable=True)  # 若生成失敗，錯誤訊息

    # 時間戳記
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    # 關聯
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    audio_file_id = db.Column(db.Integer, db.ForeignKey('audio_file.id'), nullable=False)
    transcript_id = db.Column(db.Integer, db.ForeignKey('transcript.id'), nullable=True)
    transcript = db.relationship('Transcript', backref='reports')

    def __repr__(self):
        return f'<Report {self.title}>'