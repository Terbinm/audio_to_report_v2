"""
報告生成器
負責將轉錄結果處理為格式化報告
使用 Ollama 與 LLM 交互生成報告
"""
import os
import logging
import requests
import json
import pandas as pd
import time
import threading
import queue
from datetime import datetime
from flask import current_app
from models.db_models import Report, Transcript, ReportStatus
from app import db

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("report_generator")


class ReportGeneratorException(Exception):
    """報告生成器異常"""
    pass


class ProgressReporter:
    """進度回報器，用於追蹤和報告生成進度"""

    def __init__(self, report_id, total_steps=3):
        """
        初始化進度回報器

        Args:
            report_id: 報告 ID
            total_steps: 總步驟數
        """
        self.report_id = report_id
        self.total_steps = total_steps
        self.current_step = 0
        self.step_progress = 0

    def update_step(self, step_index, message=""):
        """更新當前步驟"""
        self.current_step = step_index
        self.step_progress = 0
        self._update_db_progress()
        logger.info(f"[報告 {self.report_id}] 步驟 {step_index}/{self.total_steps}: {message}")

    def update_step_progress(self, progress, message=""):
        """更新當前步驟的進度百分比 (0-100)"""
        self.step_progress = max(0, min(100, progress))
        self._update_db_progress()
        if message:
            logger.info(f"[報告 {self.report_id}] 步驟 {self.current_step} 進度: {progress:.1f}% - {message}")

    def _update_db_progress(self):
        """更新資料庫中的進度"""
        # 計算總體進度百分比
        overall_progress = ((self.current_step - 1) * 100 + self.step_progress) / self.total_steps

        # 更新資料庫
        try:
            report = Report.query.get(self.report_id)
            if report:
                report.progress = overall_progress
                db.session.commit()
        except Exception as e:
            logger.error(f"更新進度到資料庫時發生錯誤: {e}")


class ReportGenerator:
    """報告生成器，處理轉錄結果並生成報告"""

    def __init__(self, report_id, progress_callback=None):
        """
        初始化報告生成器

        Args:
            report_id: 報告 ID
            progress_callback: 進度回調函數 (可選)
        """
        self.report_id = report_id
        self.progress_callback = progress_callback
        self.reporter = ProgressReporter(report_id)

        # 從資料庫載入報告資訊
        self.report = Report.query.get(report_id)
        if not self.report:
            raise ReportGeneratorException(f"找不到 ID 為 {report_id} 的報告")

        # 載入相關的轉錄資訊
        self.transcript = Transcript.query.get(self.report.transcript_id)
        if not self.transcript:
            raise ReportGeneratorException(f"找不到 ID 為 {self.report.transcript_id} 的轉錄")

        # 設定相關路徑
        self.app_config = current_app.config
        self.report_dir = self.app_config['REPORT_FOLDER']

        # 確保輸出目錄存在
        os.makedirs(self.report_dir, exist_ok=True)

        # 確保調試目錄存在
        debug_dir = self.app_config.get('REPORT_DEBUG_FOLDER')
        if debug_dir:
            os.makedirs(debug_dir, exist_ok=True)

        # 使用全局命名的隊列，確保跨進程共享
        self.message_queue_name = f"report_queue_{report_id}"

        # 檢查是否已存在全局隊列，如果不存在則創建
        if not hasattr(current_app, self.message_queue_name):
            setattr(current_app, self.message_queue_name, queue.Queue())

        # 獲取全局隊列
        self.message_queue = getattr(current_app, self.message_queue_name)

        # 結果內容
        self.result_content = ""

        # 設定 Ollama 連接資訊
        self.ollama_host = self.app_config.get('DEFAULT_OLLAMA_HOST', 'localhost')
        self.ollama_port = self.app_config.get('DEFAULT_OLLAMA_PORT', '11434')
        self.ollama_model = self.report.ollama_model or self.app_config.get('DEFAULT_OLLAMA_MODEL', 'phi4:14b')
        self.ollama_url = f"http://{self.ollama_host}:{self.ollama_port}/api/generate"

        # 報告相關設定
        self.system_prompt = self.report.system_prompt
        self.max_tokens = self.app_config.get('MAX_REPORT_TOKENS', 4000)

    def generate_async(self):
        """非同步生成報告"""
        # 更新報告狀態為生成中
        self.report.status = ReportStatus.GENERATING
        self.report.progress = 0
        db.session.commit()

        # 獲取應用上下文和當前報告ID
        app = current_app._get_current_object()
        report_id = self.report_id

        # 啟動生成線程，確保傳遞應用上下文
        def run_with_app_context():
            with app.app_context():
                # 在新的線程中重新獲取報告生成器對象
                generator = ReportGenerator(report_id)
                generator._generate_report()

        generate_thread = threading.Thread(target=run_with_app_context)
        generate_thread.daemon = True
        generate_thread.start()

        return True


    def _generate_report(self):
        """生成報告的主要方法"""
        try:
            # 步驟 1: 讀取和預處理轉錄數據
            self.reporter.update_step(1, "讀取和預處理轉錄資料")
            transcript_text = self._preprocess_transcript()

            # 步驟 2: 生成報告內容
            self.reporter.update_step(2, "生成報告內容")
            report_content = self._generate_content(transcript_text)

            # 步驟 3: 儲存和後處理報告
            self.reporter.update_step(3, "儲存和後處理報告")
            report_paths = self._save_report(report_content)

            # 更新完成狀態
            self.report.status = ReportStatus.COMPLETED
            self.report.completed_at = datetime.utcnow()
            self.report.markdown_path = report_paths.get('markdown_path')
            self.report.pdf_path = report_paths.get('pdf_path')
            db.session.commit()

            # 回報處理完成
            if self.progress_callback:
                self.progress_callback(100, "報告生成完成")

            logger.info(f"報告 {self.report_id} 生成完成")

        except Exception as e:
            # 處理失敗
            logger.error(f"生成報告時發生錯誤: {e}")

            self.report.status = ReportStatus.FAILED
            self.report.error_message = str(e)
            db.session.commit()

            if self.progress_callback:
                self.progress_callback(-1, f"生成失敗: {e}")

    def _preprocess_transcript(self):
        """讀取和預處理轉錄數據"""
        try:
            # 檢查 CSV 和 TXT 檔案是否存在
            csv_path = self.transcript.csv_path
            txt_path = self.transcript.txt_path

            if not os.path.exists(csv_path):
                raise ReportGeneratorException(f"找不到轉錄 CSV 檔案: {csv_path}")

            if not os.path.exists(txt_path):
                raise ReportGeneratorException(f"找不到轉錄 TXT 檔案: {txt_path}")

            # 讀取 TXT 檔案
            self.reporter.update_step_progress(30, "讀取轉錄文件")

            with open(txt_path, 'r', encoding='utf-8') as f:
                transcript_text = f.read()

            # 讀取 CSV 檔案以獲取更詳細的信息
            self.reporter.update_step_progress(50, "分析轉錄數據")

            try:
                df = pd.read_csv(csv_path, encoding='utf-8')

                # 獲取說話者數量
                speakers = df['speaker'].unique()
                speakers_count = len(speakers)

                # 獲取轉錄時長
                duration = df['end'].max() if not df.empty else 0

                # 獲取字數
                word_count = df['text'].str.split().str.len().sum()

                # 更新轉錄記錄的統計資訊
                self.transcript.speakers_count = speakers_count
                self.transcript.total_duration = duration
                self.transcript.word_count = word_count
                db.session.commit()

                # 為報告標題生成一個基本的名稱
                if not self.report.title:
                    self.report.title = f"會議報告 - {datetime.now().strftime('%Y-%m-%d')}"
                    db.session.commit()

            except Exception as e:
                logger.warning(f"分析 CSV 數據時發生錯誤: {e}")

            self.reporter.update_step_progress(100, "預處理完成")

            return transcript_text

        except Exception as e:
            logger.error(f"預處理轉錄數據時發生錯誤: {e}")
            raise ReportGeneratorException(f"預處理轉錄數據時發生錯誤: {e}")

    def _generate_content(self, transcript_text):
        """使用 Ollama 生成報告內容"""
        try:
            # 準備提示詞
            self.reporter.update_step_progress(10, "準備 LLM 提示詞")

            system_prompt = self.system_prompt
            user_prompt = f"這是一個會議的逐字稿，請根據以下內容生成一份結構良好的會議紀錄：\n\n{transcript_text}"

            # 準備 API 請求
            self.reporter.update_step_progress(20, f"連接 Ollama 服務 ({self.ollama_host}:{self.ollama_port})")

            # 從報告或設定檔獲取生成參數
            temperature = self.report.temperature if hasattr(self.report,
                                                             'temperature') and self.report.temperature is not None else self.app_config.get(
                'DEFAULT_TEMPERATURE')
            top_p = self.report.top_p if hasattr(self.report,
                                                 'top_p') and self.report.top_p is not None else self.app_config.get(
                'DEFAULT_TOP_P')
            top_k = self.report.top_k if hasattr(self.report,
                                                 'top_k') and self.report.top_k is not None else self.app_config.get(
                'DEFAULT_TOP_K')
            frequency_penalty = self.report.frequency_penalty if hasattr(self.report,
                                                                         'frequency_penalty') and self.report.frequency_penalty is not None else self.app_config.get(
                'DEFAULT_FREQUENCY_PENALTY')
            presence_penalty = self.report.presence_penalty if hasattr(self.report,
                                                                       'presence_penalty') and self.report.presence_penalty is not None else self.app_config.get(
                'DEFAULT_PRESENCE_PENALTY')
            repeat_penalty = self.report.repeat_penalty if hasattr(self.report,
                                                                   'repeat_penalty') and self.report.repeat_penalty is not None else self.app_config.get(
                'DEFAULT_REPEAT_PENALTY')
            seed = self.report.seed if hasattr(self.report,
                                               'seed') and self.report.seed is not None else self.app_config.get(
                'DEFAULT_SEED')

            headers = {"Content-Type": "application/json"}
            data = {
                "model": self.ollama_model,
                "prompt": user_prompt,
                "system": system_prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "top_p": top_p,
                    "top_k": top_k,
                }
            }

            # 只在有數值時添加這些參數，避免某些模型不支援的問題
            if frequency_penalty is not None:
                data["options"]["frequency_penalty"] = frequency_penalty

            if presence_penalty is not None:
                data["options"]["presence_penalty"] = presence_penalty

            if repeat_penalty is not None:
                data["options"]["repeat_penalty"] = repeat_penalty

            if seed is not None:
                data["options"]["seed"] = seed

            # 儲存 LLM 請求參數用於調試
            debug_dir = self.app_config.get('REPORT_DEBUG_FOLDER')
            if debug_dir:
                debug_file = os.path.join(debug_dir, f"report_{self.report_id}_request.json")
                with open(debug_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

            # 發送請求並串流接收生成內容
            self.reporter.update_step_progress(30, f"正在使用 {self.ollama_model} 生成報告")

            try:
                response = requests.post(self.ollama_url, headers=headers, json=data, stream=True)

                if response.status_code != 200:
                    error_msg = f"Ollama API 返回錯誤: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise ReportGeneratorException(error_msg)

                # 串流處理回應
                progress = 30
                progress_step = 50 / (self.max_tokens / 10)  # 每 10 個 token 更新一次進度

                tokens_received = 0
                content = ""
                response_chunks = []

                for line in response.iter_lines():
                    if line:
                        try:
                            json_line = json.loads(line)
                            response_chunks.append(json_line)  # 儲存原始回應

                            # 獲取生成的文本並添加到內容中
                            if "response" in json_line:
                                chunk = json_line["response"]
                                content += chunk

                                # 確保使用正確的全局隊列
                                queue_to_use = getattr(current_app, self.message_queue_name, self.message_queue)
                                queue_to_use.put(chunk)

                                # 調試輸出
                                logger.debug(f"添加到隊列: {chunk}")

                                # 更新 token 計數和進度
                                tokens_received += 1
                                if tokens_received % 10 == 0:
                                    progress += progress_step
                                    self.reporter.update_step_progress(
                                        min(80, progress),
                                        f"已生成 {tokens_received} 個 token"
                                    )

                            # 檢查是否完成生成
                            if json_line.get("done", False):
                                break

                        except json.JSONDecodeError:
                            logger.warning(f"無法解析 JSON: {line}")

                # 儲存 LLM 響應用於調試
                if debug_dir:
                    debug_response_file = os.path.join(debug_dir, f"report_{self.report_id}_response.json")
                    with open(debug_response_file, 'w', encoding='utf-8') as f:
                        json.dump(response_chunks, f, ensure_ascii=False, indent=2)

                    # 同時保存完整生成的內容
                    content_file = os.path.join(debug_dir, f"report_{self.report_id}_content.md")
                    with open(content_file, 'w', encoding='utf-8') as f:
                        f.write(content)

                self.reporter.update_step_progress(90, "報告生成完成")

            except requests.RequestException as e:
                error_msg = f"連接 Ollama 服務時發生錯誤: {e}"
                logger.error(error_msg)
                raise ReportGeneratorException(error_msg)

            # 儲存生成的內容
            self.result_content = content
            self.reporter.update_step_progress(100, "內容生成完成")

            return content

        except Exception as e:
            logger.error(f"生成報告內容時發生錯誤: {e}")
            raise ReportGeneratorException(f"生成報告內容時發生錯誤: {e}")

    def get_messages(self, timeout=0.5):
        """
        從消息隊列中獲取一條生成消息

        Args:
            timeout: 獲取消息的超時時間（秒）

        Returns:
            獲取到的消息，如果隊列為空則返回 None
        """
        try:
            # 確保使用正確的全局隊列
            queue_to_use = getattr(current_app, self.message_queue_name, self.message_queue)
            return queue_to_use.get(block=False)  # 嘗試非阻塞獲取
        except (queue.Empty, AttributeError):
            return None

    def _save_report(self, content):
        """儲存報告為 Markdown 和 PDF 格式"""
        try:
            # 準備基本檔案名稱
            base_name = f"report_{self.report_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 儲存 Markdown 檔案
            self.reporter.update_step_progress(30, "儲存 Markdown 報告")

            markdown_path = os.path.join(self.report_dir, f"{base_name}.md")

            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"已儲存 Markdown 報告到: {markdown_path}")

            # 嘗試生成 PDF (使用 xhtml2pdf 而非 WeasyPrint)
            pdf_path = None
            try:
                self.reporter.update_step_progress(60, "嘗試生成 PDF 報告")

                # 檢查是否有 xhtml2pdf
                pdf_generator_available = False

                try:
                    from xhtml2pdf import pisa
                    pdf_generator_available = True
                except ImportError:
                    logger.warning("未找到 xhtml2pdf 套件，無法生成 PDF 報告")

                if pdf_generator_available:
                    pdf_path = os.path.join(self.report_dir, f"{base_name}.pdf")

                    # 使用 markdown 轉換為 HTML
                    import markdown
                    html_content = markdown.markdown(content)

                    # 添加基本的 CSS 樣式
                    styled_html = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <title>{self.report.title}</title>
                        <style>
                            body {{ font-family: Arial, sans-serif; margin: 2cm; }}
                            h1 {{ color: #333366; }}
                            h2 {{ color: #333366; border-bottom: 1px solid #ddd; padding-bottom: 5px; }}
                            table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
                            th, td {{ border: 1px solid #ddd; padding: 8px; }}
                            th {{ background-color: #f2f2f2; }}
                        </style>
                    </head>
                    <body>
                        {html_content}
                    </body>
                    </html>
                    """

                    # 生成 PDF
                    with open(pdf_path, "w+b") as result_file:
                        status = pisa.CreatePDF(styled_html, dest=result_file)

                    # 檢查是否生成成功
                    if not status.err:
                        logger.info(f"已儲存 PDF 報告到: {pdf_path}")
                    else:
                        logger.error(f"生成 PDF 時發生錯誤: {status.err}")
                        pdf_path = None

            except Exception as e:
                logger.warning(f"生成 PDF 報告時發生錯誤: {e}")

            self.reporter.update_step_progress(100, "報告儲存完成")

            return {
                "markdown_path": markdown_path,
                "pdf_path": pdf_path
            }

        except Exception as e:
            logger.error(f"儲存報告時發生錯誤: {e}")
            raise ReportGeneratorException(f"儲存報告時發生錯誤: {e}")


# 工廠函式
def create_report_generator(report_id, progress_callback=None):
    """
    建立報告生成器實例

    Args:
        report_id: 報告 ID
        progress_callback: 進度回調函數 (可選)

    Returns:
        ReportGenerator 實例
    """
    return ReportGenerator(report_id, progress_callback)


# 字數統計工具
def count_words(text):
    """
    計算文本中的字數
    中文以單字為單位，英文以空格分隔的單詞為單位

    Args:
        text: 要計算的文本

    Returns:
        字數
    """
    if not text:
        return 0

    # 分割英文單詞和中文字符
    import re
    # 匹配英文單詞
    english_words = re.findall(r'[a-zA-Z]+', text)
    # 移除英文後剩下的文本（主要是中文）
    chinese_text = re.sub(r'[a-zA-Z]+', '', text)
    # 移除標點符號和空格
    chinese_text = re.sub(r'[\s\p{P}]', '', chinese_text)

    # 計算總字數
    total_words = len(english_words) + len(chinese_text)
    return total_words