"""
檔案處理工具
提供檔案操作、格式檢查等功能
"""
import os
import shutil
import uuid
import mimetypes
from werkzeug.utils import secure_filename
from flask import current_app
import logging

# 設定日誌
logger = logging.getLogger(__name__)


def allowed_file(filename, allowed_extensions=None):
    """
    檢查檔案是否為允許的格式

    Args:
        filename: 檔案名稱
        allowed_extensions: 允許的副檔名集合，如果為 None 則使用應用配置

    Returns:
        bool: 是否為允許的檔案格式
    """
    if allowed_extensions is None:
        allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', set())

    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def get_file_extension(filename):
    """
    獲取檔案副檔名

    Args:
        filename: 檔案名稱

    Returns:
        str: 檔案副檔名 (不含點號)
    """
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''


def get_mime_type(filename):
    """
    獲取檔案的 MIME 類型

    Args:
        filename: 檔案名稱

    Returns:
        str: MIME 類型
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or 'application/octet-stream'


def generate_unique_filename(original_filename):
    """
    生成唯一的檔案名稱

    Args:
        original_filename: 原始檔案名稱

    Returns:
        str: 唯一的檔案名稱
    """
    filename = secure_filename(original_filename)
    extension = get_file_extension(filename)
    unique_id = str(uuid.uuid4())

    return f"{unique_id}.{extension}" if extension else unique_id


def save_uploaded_file(file, upload_folder=None, filename=None):
    """
    保存上傳的檔案

    Args:
        file: 上傳的檔案對象
        upload_folder: 上傳目錄，如果為 None 則使用應用配置
        filename: 保存的檔案名稱，如果為 None 則使用生成的唯一檔案名稱

    Returns:
        tuple: (檔案路徑, 檔案大小)
    """
    if upload_folder is None:
        upload_folder = current_app.config.get('UPLOAD_FOLDER')

    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)

    if filename is None:
        filename = generate_unique_filename(file.filename)

    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)

    # 獲取檔案大小
    file_size = os.path.getsize(file_path)

    return file_path, file_size


def delete_file(file_path):
    """
    刪除檔案

    Args:
        file_path: 檔案路徑

    Returns:
        bool: 是否成功刪除
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        logger.error(f"刪除檔案失敗: {e}")

    return False


def copy_file(src_path, dst_path):
    """
    複製檔案

    Args:
        src_path: 源檔案路徑
        dst_path: 目標檔案路徑

    Returns:
        bool: 是否成功複製
    """
    try:
        # 確保目標目錄存在
        dst_dir = os.path.dirname(dst_path)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)

        shutil.copy2(src_path, dst_path)
        return True
    except Exception as e:
        logger.error(f"複製檔案失敗: {e}")

    return False


def ensure_dir(directory):
    """
    確保目錄存在，如果不存在則創建

    Args:
        directory: 目錄路徑

    Returns:
        bool: 是否確保成功
    """
    try:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"創建目錄失敗: {e}")

    return False


def get_file_size_str(size_in_bytes):
    """
    將檔案大小轉換為可讀的字串表示

    Args:
        size_in_bytes: 檔案大小 (位元組)

    Returns:
        str: 可讀的檔案大小字串
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0

    return f"{size_in_bytes:.2f} PB"


def get_relative_path(file_path, base_dir=None):
    """
    獲取相對路徑

    Args:
        file_path: 檔案絕對路徑
        base_dir: 基準目錄，如果為 None 則使用應用根目錄

    Returns:
        str: 相對路徑
    """
    if base_dir is None:
        base_dir = current_app.config.get('BASE_DIR')

    try:
        return os.path.relpath(file_path, base_dir)
    except Exception:
        return file_path


def get_file_metadata(file_path):
    """
    獲取檔案元數據

    Args:
        file_path: 檔案路徑

    Returns:
        dict: 檔案元數據
    """
    if not os.path.exists(file_path):
        return None

    try:
        stats = os.stat(file_path)

        return {
            'path': file_path,
            'filename': os.path.basename(file_path),
            'size': stats.st_size,
            'size_str': get_file_size_str(stats.st_size),
            'created_at': stats.st_ctime,
            'modified_at': stats.st_mtime,
            'mime_type': get_mime_type(file_path),
            'extension': get_file_extension(file_path)
        }
    except Exception as e:
        logger.error(f"獲取檔案元數據失敗: {e}")

    return None