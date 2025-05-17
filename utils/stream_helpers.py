"""
串流處理工具
提供 LLM 串流生成與 Server-Sent Events 支援
"""
import json
import logging
import time
import threading
import queue
import functools
from flask import Response, stream_with_context

# 設定日誌
logger = logging.getLogger(__name__)


def generate_sse_response(generator_func, *args, **kwargs):
    """
    生成 Server-Sent Events 響應

    Args:
        generator_func: 生成器函數，返回要串流的數據
        args, kwargs: 傳遞給生成器函數的參數

    Returns:
        Response: SSE 響應對象
    """

    @stream_with_context
    def event_stream():
        try:
            for data in generator_func(*args, **kwargs):
                if data:
                    # 格式化為 SSE 格式
                    if isinstance(data, dict):
                        data = json.dumps(data)

                    # 發送數據
                    yield f"data: {data}\n\n"

                    # 適當休眠以減輕服務器負擔
                    time.sleep(0.01)

            # 發送結束事件
            yield "event: done\ndata: done\n\n"

        except Exception as e:
            logger.error(f"串流處理發生錯誤: {e}")
            # 發送錯誤事件
            yield f"event: error\ndata: {str(e)}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


def stream_process_with_queue(queue_obj, timeout=0.1):
    """
    從隊列中獲取訊息並串流輸出

    Args:
        queue_obj: 隊列對象
        timeout: 獲取訊息的超時時間

    Yields:
        從隊列中獲取的訊息
    """
    empty_count = 0
    max_empty_count = 50  # 如果連續50次沒有獲取到訊息，則認為處理完成

    while empty_count < max_empty_count:
        try:
            data = queue_obj.get(timeout=timeout)
            if data:
                yield data
                empty_count = 0
            else:
                empty_count += 1
        except queue.Empty:
            empty_count += 1
            yield ""  # 保持連接活躍
            time.sleep(0.1)

    # 最終檢查，確保獲取全部訊息
    while not queue_obj.empty():
        try:
            data = queue_obj.get_nowait()
            if data:
                yield data
        except queue.Empty:
            break


def stream_from_ollama(ollama_host, ollama_port, model, prompt, system=None,
                       options=None, queue_obj=None, on_chunk=None):
    """
    從 Ollama API 獲取串流響應並處理

    Args:
        ollama_host: Ollama 主機地址
        ollama_port: Ollama 端口
        model: 使用的模型名稱
        prompt: 提示詞
        system: 系統提示詞 (可選)
        options: 生成選項 (可選)
        queue_obj: 用於存放響應的隊列 (可選)
        on_chunk: 處理每個 chunk 的回調函數 (可選)

    Returns:
        bool: 是否成功
    """
    import requests

    # 建立請求 URL
    url = f"http://{ollama_host}:{ollama_port}/api/generate"

    # 構建請求數據
    data = {
        "model": model,
        "prompt": prompt,
        "stream": True
    }

    if system:
        data["system"] = system

    if options:
        data["options"] = options

    # 准備請求 headers
    headers = {"Content-Type": "application/json"}

    try:
        # 發送請求
        logger.info(f"連接到 Ollama 服務 ({ollama_host}:{ollama_port})")
        logger.info(f"使用模型: {model}")

        response = requests.post(url, headers=headers, json=data, stream=True)

        # 檢查響應狀態
        if response.status_code != 200:
            logger.error(f"Ollama API 返回錯誤: {response.status_code} - {response.text}")
            return False

        # 處理響應
        content = ""

        for line in response.iter_lines():
            if line:
                try:
                    json_line = json.loads(line)

                    # 獲取生成的文本
                    if "response" in json_line:
                        chunk = json_line["response"]
                        content += chunk

                        # 如果提供了隊列，將 chunk 加入隊列
                        if queue_obj is not None:
                            queue_obj.put(chunk)

                        # 如果提供了回調函數，調用回調
                        if on_chunk is not None:
                            on_chunk(chunk)

                    # 檢查是否完成生成
                    if json_line.get("done", False):
                        break

                except json.JSONDecodeError:
                    logger.warning(f"無法解析 JSON: {line}")

        # 返回成功標誌
        return True

    except Exception as e:
        logger.error(f"連接 Ollama 服務時發生錯誤: {e}")
        return False


def run_in_background(func):
    """
    將函數在背景線程中運行的裝飾器

    Args:
        func: 要在背景運行的函數

    Returns:
        裝飾後的函數
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        return thread

    return wrapper


class StreamBuffer:
    """串流緩衝器，用於 LLM 輸出的緩存和串流"""

    def __init__(self):
        """初始化緩衝器"""
        self.buffer = queue.Queue()
        self.complete = False
        self.error = None

    def add(self, chunk):
        """添加一個 chunk 到緩衝器"""
        if chunk:
            self.buffer.put(chunk)

    def get(self, timeout=0.1):
        """從緩衝器獲取一個 chunk"""
        try:
            return self.buffer.get(timeout=timeout)
        except queue.Empty:
            return None

    def mark_complete(self):
        """標記緩衝器完成"""
        self.complete = True

    def mark_error(self, error_msg):
        """標記錯誤"""
        self.error = error_msg
        self.complete = True

    def is_complete(self):
        """檢查緩衝器是否已完成"""
        return self.complete

    def has_error(self):
        """檢查是否有錯誤"""
        return self.error is not None

    def get_error(self):
        """獲取錯誤訊息"""
        return self.error

    def is_empty(self):
        """檢查緩衝器是否為空"""
        return self.buffer.empty()

    def stream(self):
        """串流輸出緩衝器中的內容"""
        empty_count = 0
        max_empty_count = 30  # 如果連續30次沒有獲取到訊息且標記為完成，則結束

        while not (self.complete and empty_count >= max_empty_count):
            chunk = self.get()

            if chunk:
                yield {"status": "ok", "chunk": chunk}
                empty_count = 0
            else:
                empty_count += 1
                time.sleep(0.1)

        # 檢查是否有錯誤
        if self.has_error():
            yield {"status": "error", "message": self.get_error()}
        else:
            yield {"status": "done"}