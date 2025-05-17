"""
音訊處理器
基於 wav_to_transcript.py 的功能，用於音訊檔案的處理、轉錄與說話者分割
"""
import os
import torch
import whisper
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pyannote.audio import Pipeline
from pyannote.audio.pipelines.utils.hook import ProgressHook
from pydub import AudioSegment
import datetime
import sys
import logging
from pathlib import Path
import warnings
import librosa
import soundfile as sf
import threading
import queue
from flask import current_app
from models.db_models import AudioFile, Transcript, ProcessingStatus, TranscriptStatus
from app import db

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("audio_processor")

# 忽略非關鍵警告
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


class AudioProcessorException(Exception):
    """音訊處理器異常"""
    pass


class ProgressReporter:
    """進度回報器，用於追蹤和報告處理進度"""

    def __init__(self, audio_file_id, total_steps=5):
        """
        初始化進度回報器

        Args:
            audio_file_id: 音訊檔案 ID
            total_steps: 總步驟數
        """
        self.audio_file_id = audio_file_id
        self.total_steps = total_steps
        self.current_step = 0
        self.step_progress = 0

    def update_step(self, step_index, message=""):
        """更新當前步驟"""
        self.current_step = step_index
        self.step_progress = 0
        self._update_db_progress()
        logger.info(f"[檔案 {self.audio_file_id}] 步驟 {step_index}/{self.total_steps}: {message}")

    def update_step_progress(self, progress, message=""):
        """更新當前步驟的進度百分比 (0-100)"""
        self.step_progress = max(0, min(100, progress))
        self._update_db_progress()
        if message:
            logger.info(f"[檔案 {self.audio_file_id}] 步驟 {self.current_step} 進度: {progress:.1f}% - {message}")

    def _update_db_progress(self):
        """更新資料庫中的進度"""
        # 計算總體進度百分比
        overall_progress = ((self.current_step - 1) * 100 + self.step_progress) / self.total_steps

        # 更新資料庫
        try:
            audio_file = AudioFile.query.get(self.audio_file_id)
            if audio_file:
                audio_file.progress = overall_progress
                if self.current_step == self.total_steps and self.step_progress == 100:
                    audio_file.status = ProcessingStatus.COMPLETED
                    audio_file.processed_at = datetime.datetime.now(datetime.UTC)

                db.session.commit()
        except Exception as e:
            logger.error(f"更新進度到資料庫時發生錯誤: {e}")


class AudioProcessor:
    """音訊處理器類別，處理音訊檔案、轉錄與說話者分割"""

    def __init__(self, audio_file_id, progress_callback=None):
        """
        初始化音訊處理器

        Args:
            audio_file_id: 音訊檔案 ID
            progress_callback: 進度回調函數 (可選)
        """
        self.audio_file_id = audio_file_id
        self.progress_callback = progress_callback
        self.reporter = ProgressReporter(audio_file_id)

        # 從資料庫載入音訊檔案資訊
        self.audio_file = AudioFile.query.get(audio_file_id)
        if not self.audio_file:
            raise AudioProcessorException(f"找不到 ID 為 {audio_file_id} 的音訊檔案")

        # 設定相關路徑
        self.app_config = current_app.config

        # 獲取上傳 ID (從檔案路徑的目錄名稱)
        self.upload_id = os.path.basename(os.path.dirname(self.audio_file.file_path))

        # 設定輸出目錄為上傳 ID 專屬的子目錄
        self.output_dir = os.path.join(self.app_config['OUTPUT_FOLDER'], self.upload_id)
        self.transcript_dir = os.path.join(self.app_config['TRANSCRIPT_FOLDER'], self.upload_id)
        self.visualization_dir = os.path.join(self.app_config['VISUALIZATION_FOLDER'], self.upload_id)

        # 複製可視化圖表到靜態目錄的子目錄
        self.static_visualization_dir = os.path.join(self.app_config['STATIC_VISUALIZATION_FOLDER'], self.upload_id)

        # 確保輸出目錄存在
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.transcript_dir, exist_ok=True)
        os.makedirs(self.visualization_dir, exist_ok=True)
        os.makedirs(self.static_visualization_dir, exist_ok=True)

        # 設定進度回報
        self.progress_queue = queue.Queue()

        # 其他變數，會在處理過程中設定
        self.whisper_model = None
        self.diarization_pipeline = None

    def process_async(self):
        """非同步處理音訊檔案"""
        # 更新音訊檔案狀態為處理中
        self.audio_file.status = ProcessingStatus.PROCESSING
        self.audio_file.progress = 0
        db.session.commit()

        # 獲取應用上下文和當前音訊檔案ID
        app = current_app._get_current_object()
        audio_file_id = self.audio_file_id

        # 啟動處理線程
        def run_with_app_context():
            with app.app_context():
                # 在新的線程中重新獲取音訊檔案對象
                processor = AudioProcessor(audio_file_id)
                processor._process_audio_file()

        process_thread = threading.Thread(target=run_with_app_context)
        process_thread.daemon = True
        process_thread.start()

        return True

    def _process_audio_file(self):
        """處理音訊檔案的主要方法"""
        try:
            # 步驟 1: 載入模型
            self.reporter.update_step(1, "初始化和載入模型")
            self._load_models()

            # 步驟 2: 預處理音訊
            self.reporter.update_step(2, "預處理音訊檔案")
            processed_audio = self._preprocess_audio()

            # 步驟 3: 執行語音轉文字
            self.reporter.update_step(3, "執行語音轉文字")
            transcription = self._transcribe_audio(processed_audio)

            # 步驟 4: 執行說話者分割
            self.reporter.update_step(4, "執行說話者分割")
            diarization = self._diarize_audio(processed_audio)

            # 步驟 5: 整合結果並生成輸出
            self.reporter.update_step(5, "整合結果並生成輸出")
            final_result = self._integrate_results(transcription, diarization)

            # 更新完成狀態
            self.audio_file.status = ProcessingStatus.COMPLETED
            self.audio_file.processed_at = datetime.datetime.now(datetime.UTC)

            db.session.commit()

            # 回報處理完成
            if self.progress_callback:
                self.progress_callback(100, "處理完成")

            logger.info(f"音訊檔案 {self.audio_file.original_filename} 處理完成")

        except Exception as e:
            # 處理失敗
            logger.error(f"處理音訊檔案時發生錯誤: {e}")

            self.audio_file.status = ProcessingStatus.FAILED
            self.audio_file.error_message = str(e)
            db.session.commit()

            if self.progress_callback:
                self.progress_callback(-1, f"處理失敗: {e}")

    def _load_models(self):
        """載入 Whisper 和 Pyannote 模型"""
        try:
            # 設定設備
            device = self.audio_file.device if hasattr(self.audio_file, 'device') else (
                    self.app_config.get('DEVICE') or ("cuda" if torch.cuda.is_available() else "cpu")
            )
            logger.info(f"使用設備: {device}")

            # 載入 Whisper 模型
            whisper_model_name = self.audio_file.whisper_model or self.app_config.get('DEFAULT_WHISPER_MODEL', 'base')
            self.reporter.update_step_progress(10, f"載入 Whisper {whisper_model_name} 模型")

            logger.info(f"正在載入 Whisper {whisper_model_name} 模型...")
            self.whisper_model = whisper.load_model(whisper_model_name)
            logger.info("Whisper 模型載入完成")

            # 載入 Pyannote 模型
            self.reporter.update_step_progress(50, "載入說話者分割模型")

            hf_token = self.app_config.get('DEFAULT_HF_TOKEN')
            logger.info("正在載入說話者分割模型...")

            try:
                if hf_token:
                    self.diarization_pipeline = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.0",
                        use_auth_token=hf_token
                    ).to(torch.device(device))
                else:
                    logger.warning("未提供 HuggingFace token，將嘗試使用預先下載的模型或公開訪問")
                    self.diarization_pipeline = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.0"
                    ).to(torch.device(device))

                logger.info("說話者分割模型載入完成")

            except Exception as e:
                logger.error(f"載入說話者分割模型時發生錯誤: {e}")
                raise AudioProcessorException(f"無法載入說話者分割模型: {e}")

            self.reporter.update_step_progress(100, "模型載入完成")

        except Exception as e:
            logger.error(f"載入模型時發生錯誤: {e}")
            raise AudioProcessorException(f"載入模型時發生錯誤: {e}")

    def _preprocess_audio(self):
        """預處理音訊檔案，如有需要則轉換為單聲道"""
        try:
            audio_path = self.audio_file.file_path

            # 檢查檔案是否存在
            if not os.path.exists(audio_path):
                raise AudioProcessorException(f"找不到音訊檔案: {audio_path}")

            # 獲取音訊資訊
            self.reporter.update_step_progress(25, "讀取音訊檔案資訊")
            wav_info = self._get_wav_info(audio_path)

            if wav_info is None:
                raise AudioProcessorException("無法讀取音訊檔案資訊")

            logger.info(f"處理音訊檔案: {audio_path}")
            logger.info(f"音訊資訊: 時長={wav_info['duration']:.2f}秒, "
                        f"取樣率={wav_info['sample_rate']}Hz, "
                        f"聲道數={wav_info['n_channels']}")

            # 更新音訊檔案的時長
            self.audio_file.duration = wav_info['duration']
            db.session.commit()

            # 如果是多聲道，轉換為單聲道
            self.reporter.update_step_progress(50, "檢查並轉換為單聲道")

            if wav_info['n_channels'] > 1:
                logger.info("檢測到多聲道音訊，正在轉換為單聲道...")

                # 準備單聲道檔案路徑
                base_name = os.path.splitext(os.path.basename(audio_path))[0]
                mono_path = os.path.join(self.output_dir, f"{base_name}_mono.wav")

                # 轉換為單聲道
                mono_path = self._convert_to_mono(audio_path, mono_path)

                self.reporter.update_step_progress(100, "預處理完成，已轉換為單聲道")
                return mono_path

            # 如果已經是單聲道，直接返回原始路徑
            self.reporter.update_step_progress(100, "預處理完成，已是單聲道")
            return audio_path

        except Exception as e:
            logger.error(f"預處理音訊檔案時發生錯誤: {e}")
            raise AudioProcessorException(f"預處理音訊檔案時發生錯誤: {e}")

    def _get_wav_info(self, wav_file):
        """獲取音訊檔案資訊"""
        try:
            # 使用 librosa 載入音訊檔案
            y, sr = librosa.load(wav_file, sr=None, mono=False)

            # 計算音訊時長
            duration = librosa.get_duration(y=y, sr=sr)

            # 確定聲道數
            if y.ndim > 1:
                n_channels = y.shape[0]
            else:
                n_channels = 1

            return {
                "sample_rate": sr,
                "sample_width": 2,  # 假設 16 位元 (2 bytes)
                "n_channels": n_channels,
                "n_frames": len(y) if n_channels == 1 else len(y[0]),
                "duration": duration
            }
        except Exception as e:
            logger.error(f"讀取音訊檔案資訊失敗: {e}")
            return None

    def _convert_to_mono(self, wav_file, output_path=None):
        """將音訊檔案轉換為單聲道"""
        try:
            if output_path is None:
                base_name = os.path.splitext(wav_file)[0]
                output_path = f"{base_name}_mono.wav"

            # 使用 librosa 取得音訊資料
            y, sr = librosa.load(wav_file, sr=None, mono=False)

            # 檢查是否已是單聲道
            if y.ndim == 1 or (y.ndim > 1 and y.shape[0] == 1):
                logger.info("檔案已是單聲道，無需轉換")
                return wav_file

            # 轉換為單聲道
            logger.info(f"將 {wav_file} 轉換為單聲道")
            mono_y = librosa.to_mono(y)

            # 使用 soundfile 儲存檔案
            sf.write(output_path, mono_y, sr, subtype='PCM_16')

            logger.info(f"單聲道檔案已儲存至 {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"轉換檔案為單聲道時發生錯誤: {e}")
            # 如果失敗，嘗試使用 pydub
            try:
                logger.info("嘗試使用 pydub 轉換為單聲道...")
                audio = AudioSegment.from_file(wav_file)
                mono_audio = audio.set_channels(1)
                mono_audio.export(output_path, format="wav")
                logger.info(f"使用 pydub 轉換成功，檔案儲存至 {output_path}")
                return output_path
            except Exception as e2:
                logger.error(f"使用 pydub 轉換檔案為單聲道時發生錯誤: {e2}")
                return wav_file

    def _transcribe_audio(self, audio_path):
        """使用 Whisper 模型進行語音轉文字"""
        try:
            # 準備轉錄選項
            transcribe_options = {}
            language = self.audio_file.language or self.app_config.get('DEFAULT_LANGUAGE')

            if language:
                transcribe_options["language"] = language

            # 執行轉錄
            self.reporter.update_step_progress(10, "開始轉錄")
            logger.info(f"使用 Whisper 轉錄音訊: {audio_path}")

            result = self.whisper_model.transcribe(
                audio_path,
                verbose=False,
                **transcribe_options
            )

            self.reporter.update_step_progress(100, "轉錄完成")
            logger.info("Whisper 轉錄完成")

            return result

        except Exception as e:
            logger.error(f"轉錄音訊時發生錯誤: {e}")
            raise AudioProcessorException(f"轉錄音訊時發生錯誤: {e}")

    def _diarize_audio(self, audio_path):
        """使用 Pyannote 進行說話者分割"""
        try:
            # 準備分割選項
            diarization_options = {}

            # 設定說話者數量參數
            speakers_count = self.audio_file.speakers_count
            speaker_min = self.audio_file.speaker_min or self.app_config.get('DEFAULT_SPEAKER_MIN')
            speaker_max = self.audio_file.speaker_max or self.app_config.get('DEFAULT_SPEAKER_MAX')

            if speakers_count is not None:
                diarization_options["num_speakers"] = speakers_count
            else:
                if speaker_min is not None:
                    diarization_options["min_speakers"] = speaker_min
                if speaker_max is not None:
                    diarization_options["max_speakers"] = speaker_max

            # 執行說話者分割
            self.reporter.update_step_progress(10, "開始說話者分割")
            logger.info(f"使用 Pyannote 進行說話者分割: {audio_path}")
            logger.info(f"分割選項: {diarization_options}")

            # 直接執行分割，不使用 ProgressHook
            diarization_result = self.diarization_pipeline(
                audio_path,
                **diarization_options
            )

            # 更新進度為100%
            self.reporter.update_step_progress(100, "說話者分割完成")
            logger.info("說話者分割完成")

            return diarization_result

        except Exception as e:
            logger.error(f"說話者分割時發生錯誤: {e}")
            raise AudioProcessorException(f"說話者分割時發生錯誤: {e}")

    def _integrate_results(self, transcription, diarization):
        """整合轉錄結果和說話者分割結果，生成最終輸出"""
        try:
            # 進度報告
            self.reporter.update_step_progress(10, "開始整合結果")

            # 準備基本檔案名稱
            base_name = os.path.splitext(os.path.basename(self.audio_file.original_filename))[0]

            # 收集 Whisper 分段結果
            transcript_segments = []
            for segment in transcription["segments"]:
                transcript_segments.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"].strip()
                })

            self.reporter.update_step_progress(30, "處理說話者分割結果")

            # 收集說話者分割結果
            speaker_segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                speaker_segments.append({
                    "start": turn.start,
                    "end": turn.end,
                    "speaker": speaker
                })

            self.reporter.update_step_progress(50, "合併轉錄與說話者資訊")

            # 合併結果
            final_segments = []
            for ts in transcript_segments:
                # 找出與此文字段重疊最多的說話者
                max_overlap = 0
                assigned_speaker = "unknown"

                for ss in speaker_segments:
                    # 計算重疊時間
                    overlap_start = max(ts["start"], ss["start"])
                    overlap_end = min(ts["end"], ss["end"])
                    overlap = max(0, overlap_end - overlap_start)

                    if overlap > max_overlap:
                        max_overlap = overlap
                        assigned_speaker = ss["speaker"]

                # 加入最終結果
                final_segments.append({
                    "start": ts["start"],
                    "end": ts["end"],
                    "speaker": assigned_speaker,
                    "text": ts["text"]
                })

            # 轉換為 DataFrame
            df = pd.DataFrame(final_segments)

            self.reporter.update_step_progress(70, "生成輸出檔案")

            # 儲存 CSV 檔案
            csv_path = os.path.join(self.transcript_dir, f"{base_name}_transcript.csv")
            df.to_csv(csv_path, index=False, encoding="utf-8")
            logger.info(f"已儲存 CSV 轉錄結果到: {csv_path}")

            # 產生文字格式轉錄稿
            txt_path = os.path.join(self.transcript_dir, f"{base_name}_transcript.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f"檔案: {self.audio_file.original_filename}\n")
                f.write(f"轉錄日期: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("-" * 60 + "\n\n")

                current_speaker = None
                for _, row in df.iterrows():
                    time_str = f"[{self._format_time(row['start'])} - {self._format_time(row['end'])}]"

                    # 只有當說話者變更時才顯示說話者
                    if row['speaker'] != current_speaker:
                        current_speaker = row['speaker']
                        f.write(f"\n{row['speaker']}:\n")

                    f.write(f"{time_str} {row['text']}\n")

            logger.info(f"已儲存文字轉錄結果到: {txt_path}")

            # 生成可視化圖表
            visualize = self.app_config.get('DEFAULT_VISUALIZE', True)
            visualization_path = None

            if visualize:
                self.reporter.update_step_progress(80, "生成可視化圖表")
                visualization_path = self._visualize_diarization(df, base_name)

            # 建立轉錄記錄
            self.reporter.update_step_progress(90, "更新資料庫記錄")

            transcript = Transcript(
                audio_file_id=self.audio_file_id,
                csv_path=csv_path,
                txt_path=txt_path,
                visualization_path=visualization_path,
                total_duration=self.audio_file.duration,
                speakers_count=len(df['speaker'].unique()),
                word_count=sum(len(text.split()) for text in df['text']),
                status=TranscriptStatus.ORIGINAL
            )

            db.session.add(transcript)
            db.session.commit()

            # 複製可視化圖表到靜態目錄，以便網頁訪問
            if visualization_path:
                static_viz_path = os.path.join(self.static_visualization_dir, os.path.basename(visualization_path))
                import shutil
                shutil.copy2(visualization_path, static_viz_path)

            self.reporter.update_step_progress(100, "處理完成")
            logger.info(f"音訊檔案 {self.audio_file.original_filename} 處理完成！")

            return {
                "transcript_id": transcript.id,
                "csv_path": csv_path,
                "txt_path": txt_path,
                "visualization_path": visualization_path,
                "speakers_count": transcript.speakers_count,
                "word_count": transcript.word_count
            }

        except Exception as e:
            logger.error(f"整合結果時發生錯誤: {e}")
            raise AudioProcessorException(f"整合結果時發生錯誤: {e}")

    def _format_time(self, seconds):
        """將秒數格式化為時:分:秒.毫秒格式"""
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d}.{int((seconds % 1) * 1000):03d}"

    def _visualize_diarization(self, df, base_name):
        """生成說話者分割的可視化圖表"""
        try:
            logger.info("生成說話者分割可視化圖表...")

            plot_path = os.path.join(self.visualization_dir, f"{base_name}_diarization.png")

            # 獲取不同的說話者
            speakers = df['speaker'].unique()
            colors = plt.cm.tab10(np.linspace(0, 1, len(speakers)))
            speaker_colors = dict(zip(speakers, colors))

            # 設定圖表
            plt.figure(figsize=(12, 6))
            plt.title("Speech Diarization Visualization")
            plt.xlabel("Time (seconds)")
            plt.ylabel("Speaker")

            # 對每個說話者繪製時間軸
            for speaker in speakers:
                speaker_df = df[df['speaker'] == speaker]
                for _, row in speaker_df.iterrows():
                    plt.hlines(
                        y=speaker,
                        xmin=row['start'],
                        xmax=row['end'],
                        colors=speaker_colors[speaker],
                        linewidth=6
                    )

            # 添加網格和圖例
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.tight_layout()

            # 儲存圖表
            plt.savefig(plot_path, dpi=300, bbox_inches='tight')
            plt.close()

            logger.info(f"已儲存可視化圖表到: {plot_path}")

            return plot_path

        except Exception as e:
            logger.error(f"生成可視化圖表時發生錯誤: {e}")
            return None


# 工廠函式
def create_audio_processor(audio_file_id, progress_callback=None):
    """
    建立音訊處理器實例

    Args:
        audio_file_id: 音訊檔案 ID
        progress_callback: 進度回調函數 (可選)

    Returns:
        AudioProcessor 實例
    """
    return AudioProcessor(audio_file_id, progress_callback)