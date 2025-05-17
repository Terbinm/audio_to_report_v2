"""
音訊處理相關路由
處理音訊檔案上傳、處理和轉錄編輯功能
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, \
    send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models.db_models import AudioFile, Transcript, ProcessingStatus, TranscriptStatus
from processors.audio_processor import create_audio_processor
from app import db
import os
import datetime
import pandas as pd
import json
import threading
import uuid

# 創建藍圖
audio = Blueprint('audio', __name__)


def allowed_file(filename):
    """檢查檔案是否為允許的音訊格式"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@audio.route('/upload', methods=['GET'])
@login_required
def upload_form():
    """顯示音訊上傳表單"""
    # 獲取配置參數以供前端使用
    whisper_models = ['tiny', 'base', 'small', 'medium', 'large']
    languages = [
        {'code': None, 'name': '自動檢測'},
        {'code': 'zh', 'name': '中文'},
        {'code': 'en', 'name': '英文'},
        {'code': 'ja', 'name': '日文'},
        {'code': 'ko', 'name': '韓文'}
    ]

    return render_template(
        'upload.html',
        whisper_models=whisper_models,
        languages=languages,
        default_whisper_model=current_app.config.get('DEFAULT_WHISPER_MODEL'),
        default_language=current_app.config.get('DEFAULT_LANGUAGE'),
        default_speakers_count=current_app.config.get('DEFAULT_SPEAKERS_COUNT'),
        default_speaker_min=current_app.config.get('DEFAULT_SPEAKER_MIN'),
        default_speaker_max=current_app.config.get('DEFAULT_SPEAKER_MAX')
    )


@audio.route('/upload', methods=['POST'])
@login_required
def upload_audio():
    """處理音訊上傳請求"""
    # 檢查是否有檔案
    if 'audio_file' not in request.files:
        flash('未選擇檔案', 'error')
        return redirect(request.url)

    file = request.files['audio_file']

    # 檢查檔案名稱
    if file.filename == '':
        flash('未選擇檔案', 'error')
        return redirect(request.url)

    # 檢查檔案類型
    if not allowed_file(file.filename):
        flash(f'不支援的檔案類型。允許的類型: {", ".join(current_app.config["ALLOWED_EXTENSIONS"])}', 'error')
        return redirect(request.url)

    # 為此次上傳建立唯一識別碼
    upload_id = str(uuid.uuid4())

    # 創建該上傳的專屬資料夾
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], upload_id)
    os.makedirs(upload_folder, exist_ok=True)

    # 同時為輸出創建對應的資料夾結構
    transcript_folder = os.path.join(current_app.config['TRANSCRIPT_FOLDER'], upload_id)
    visualization_folder = os.path.join(current_app.config['VISUALIZATION_FOLDER'], upload_id)
    report_folder = os.path.join(current_app.config['REPORT_FOLDER'], upload_id)

    os.makedirs(transcript_folder, exist_ok=True)
    os.makedirs(visualization_folder, exist_ok=True)
    os.makedirs(report_folder, exist_ok=True)

    # 保存檔案
    filename = secure_filename(file.filename)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    file_path = os.path.join(upload_folder, unique_filename)

    file.save(file_path)

    # 獲取參數
    whisper_model = request.form.get('whisper_model') or current_app.config.get('DEFAULT_WHISPER_MODEL')
    language = request.form.get('language') or current_app.config.get('DEFAULT_LANGUAGE')

    try:
        speakers_count = int(request.form.get('speakers_count')) if request.form.get('speakers_count') else None
    except ValueError:
        speakers_count = None

    try:
        speaker_min = int(request.form.get('speaker_min')) if request.form.get(
            'speaker_min') else current_app.config.get('DEFAULT_SPEAKER_MIN')
    except ValueError:
        speaker_min = current_app.config.get('DEFAULT_SPEAKER_MIN')

    try:
        speaker_max = int(request.form.get('speaker_max')) if request.form.get(
            'speaker_max') else current_app.config.get('DEFAULT_SPEAKER_MAX')
    except ValueError:
        speaker_max = current_app.config.get('DEFAULT_SPEAKER_MAX')

    # 獲取檔案大小
    file_size = os.path.getsize(file_path)

    # 創建資料庫記錄
    audio_file = AudioFile(
        filename=unique_filename,
        original_filename=filename,
        file_path=file_path,
        file_size=file_size,
        whisper_model=whisper_model,
        language=language,
        speakers_count=speakers_count,
        speaker_min=speaker_min,
        speaker_max=speaker_max,
        status=ProcessingStatus.PENDING,
        user_id=current_user.id
    )

    db.session.add(audio_file)
    db.session.commit()

    # 開始處理
    return redirect(url_for('audio.process', audio_id=audio_file.id))


@audio.route('/process/<int:audio_id>')
@login_required
def process(audio_id):
    """顯示音訊處理頁面"""
    # 檢查音訊檔案是否存在且屬於當前用戶
    audio_file = AudioFile.query.filter_by(id=audio_id, user_id=current_user.id).first_or_404()

    # 如果狀態為待處理，啟動處理
    if audio_file.status == ProcessingStatus.PENDING:
        # 創建音訊處理器
        processor = create_audio_processor(audio_id)

        # 啟動非同步處理
        processor.process_async()

        # 重定向到進度頁面
        return redirect(url_for('audio.processing_status', audio_id=audio_id))

    # 如果已經在處理中，重定向到進度頁面
    elif audio_file.status == ProcessingStatus.PROCESSING:
        return redirect(url_for('audio.processing_status', audio_id=audio_id))

    # 如果處理失敗，顯示錯誤訊息
    elif audio_file.status == ProcessingStatus.FAILED:
        flash(f'處理失敗: {audio_file.error_message}', 'error')
        return redirect(url_for('auth.dashboard'))

    # 如果處理已完成，重定向到轉錄頁面
    elif audio_file.status == ProcessingStatus.COMPLETED:
        # 找到對應的轉錄記錄
        transcript = Transcript.query.filter_by(audio_file_id=audio_id).first()

        if transcript:
            return redirect(url_for('audio.view_transcript', transcript_id=transcript.id))
        else:
            flash('找不到對應的轉錄記錄', 'error')
            return redirect(url_for('auth.dashboard'))

    # 其他情況
    flash('無效的音訊處理狀態', 'error')
    return redirect(url_for('auth.dashboard'))


@audio.route('/processing_status/<int:audio_id>')
@login_required
def processing_status(audio_id):
    """顯示音訊處理進度頁面"""
    audio_file = AudioFile.query.filter_by(id=audio_id, user_id=current_user.id).first_or_404()
    return render_template('processing.html', audio_file=audio_file)


@audio.route('/processing_status/<int:audio_id>/check')
@login_required
def check_processing_status(audio_id):
    """檢查音訊處理進度 (AJAX)"""
    audio_file = AudioFile.query.filter_by(id=audio_id, user_id=current_user.id).first_or_404()

    # 檢查處理是否完成
    if audio_file.status == ProcessingStatus.COMPLETED:
        # 找到對應的轉錄記錄
        transcript = Transcript.query.filter_by(audio_file_id=audio_id).first()

        if transcript:
            redirect_url = url_for('audio.view_transcript', transcript_id=transcript.id)
        else:
            redirect_url = url_for('auth.dashboard')

        return jsonify({
            'status': 'completed',
            'progress': 100,
            'message': '處理完成',
            'redirect_url': redirect_url
        })

    # 檢查處理是否失敗
    elif audio_file.status == ProcessingStatus.FAILED:
        return jsonify({
            'status': 'failed',
            'message': audio_file.error_message,
            'redirect_url': url_for('auth.dashboard')
        })

    # 處理中
    elif audio_file.status == ProcessingStatus.PROCESSING:
        return jsonify({
            'status': 'processing',
            'progress': audio_file.progress,
            'message': f'處理中... {audio_file.progress:.1f}%'
        })

    # 其他狀態
    else:
        return jsonify({
            'status': audio_file.status.value,
            'progress': audio_file.progress
        })


@audio.route('/transcripts')
@login_required
def list_transcripts():
    """列出用戶的所有轉錄記錄"""
    transcripts = Transcript.query.join(AudioFile).filter(AudioFile.user_id == current_user.id).all()
    return render_template('transcripts_list.html', transcripts=transcripts)


@audio.route('/transcript/<int:transcript_id>')
@login_required
def view_transcript(transcript_id):
    """查看轉錄結果"""
    transcript = Transcript.query.join(AudioFile).filter(
        Transcript.id == transcript_id,
        AudioFile.user_id == current_user.id
    ).first_or_404()

    # 讀取轉錄內容
    txt_content = ""
    if transcript.txt_path and os.path.exists(transcript.txt_path):
        with open(transcript.txt_path, 'r', encoding='utf-8') as f:
            txt_content = f.read()

    # 獲取視覺化路徑 (靜態路徑，用於網頁顯示)
    visualization_url = None
    if transcript.visualization_path:
        viz_filename = os.path.basename(transcript.visualization_path)
        # 提取上傳 ID 從路徑中
        upload_id = os.path.basename(os.path.dirname(transcript.visualization_path))
        visualization_url = url_for('static', filename=f'outputs/visualizations/{upload_id}/{viz_filename}')

    return render_template(
        'transcript.html',
        transcript=transcript,
        audio_file=transcript.audio_file,
        txt_content=txt_content,
        visualization_url=visualization_url
    )


@audio.route('/transcript/<int:transcript_id>/edit', methods=['GET'])
@login_required
def edit_transcript(transcript_id):
    """編輯轉錄結果頁面"""
    transcript = Transcript.query.join(AudioFile).filter(
        Transcript.id == transcript_id,
        AudioFile.user_id == current_user.id
    ).first_or_404()

    # 讀取 CSV 內容
    csv_data = []
    if transcript.csv_path and os.path.exists(transcript.csv_path):
        try:
            df = pd.read_csv(transcript.csv_path, encoding='utf-8')
            csv_data = df.to_dict('records')
        except Exception as e:
            flash(f'讀取 CSV 檔案時發生錯誤: {e}', 'error')

    return render_template(
        'edit_transcript.html',
        transcript=transcript,
        audio_file=transcript.audio_file,
        csv_data=json.dumps(csv_data)
    )


@audio.route('/transcript/<int:transcript_id>/edit', methods=['POST'])
@login_required
def save_transcript(transcript_id):
    """保存編輯後的轉錄結果"""
    transcript = Transcript.query.join(AudioFile).filter(
        Transcript.id == transcript_id,
        AudioFile.user_id == current_user.id
    ).first_or_404()

    try:
        # 獲取編輯後的 CSV 數據
        data = request.get_json()

        if not data or 'rows' not in data:
            return jsonify({'status': 'error', 'message': '無效的數據格式'}), 400

        rows = data['rows']

        # 轉換為 DataFrame
        df = pd.DataFrame(rows)

        # 保存為 CSV
        # 從原始路徑中提取上傳 ID
        upload_id = os.path.basename(os.path.dirname(transcript.csv_path))
        transcript_folder = os.path.join(current_app.config['TRANSCRIPT_FOLDER'], upload_id)
        edited_csv_path = os.path.join(transcript_folder, f"{os.path.basename(transcript.csv_path).split('.')[0]}_edited.csv")
        df.to_csv(edited_csv_path, index=False, encoding='utf-8')

        # 生成文字格式轉錄稿
        edited_txt_path = os.path.join(transcript_folder, f"{os.path.basename(transcript.txt_path).split('.')[0]}_edited.txt")
        with open(edited_txt_path, 'w', encoding='utf-8') as f:
            f.write(f"檔案: {transcript.audio_file.original_filename} (編輯版)\n")
            f.write(f"編輯日期: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 60 + "\n\n")

            current_speaker = None
            for _, row in df.iterrows():
                time_str = f"[{_format_time(row['start'])} - {_format_time(row['end'])}]"

                # 只有當說話者變更時才顯示說話者
                if row['speaker'] != current_speaker:
                    current_speaker = row['speaker']
                    f.write(f"\n{row['speaker']}:\n")

                f.write(f"{time_str} {row['text']}\n")

        # 更新轉錄記錄
        transcript.csv_path = edited_csv_path
        transcript.txt_path = edited_txt_path
        transcript.status = TranscriptStatus.EDITED
        transcript.updated_at = datetime.datetime.now(datetime.UTC)

        # 更新字數統計
        transcript.word_count = sum(len(str(row['text']).split()) for row in rows)

        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': '轉錄已成功保存',
            'redirect_url': url_for('audio.view_transcript', transcript_id=transcript.id)
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'保存失敗: {str(e)}'}), 500


@audio.route('/transcript/<int:transcript_id>/download/<format>')
@login_required
def download_transcript(transcript_id, format):
    """下載轉錄結果"""
    transcript = Transcript.query.join(AudioFile).filter(
        Transcript.id == transcript_id,
        AudioFile.user_id == current_user.id
    ).first_or_404()

    if format == 'txt':
        # 下載 TXT 檔案
        if not transcript.txt_path or not os.path.exists(transcript.txt_path):
            flash('轉錄 TXT 檔案不存在', 'error')
            return redirect(url_for('audio.view_transcript', transcript_id=transcript.id))

        directory = os.path.dirname(transcript.txt_path)
        filename = os.path.basename(transcript.txt_path)

        return send_from_directory(
            directory,
            filename,
            as_attachment=True,
            download_name=f"{transcript.audio_file.original_filename.split('.')[0]}_transcript.txt"
        )

    elif format == 'csv':
        # 下載 CSV 檔案
        if not transcript.csv_path or not os.path.exists(transcript.csv_path):
            flash('轉錄 CSV 檔案不存在', 'error')
            return redirect(url_for('audio.view_transcript', transcript_id=transcript.id))

        directory = os.path.dirname(transcript.csv_path)
        filename = os.path.basename(transcript.csv_path)

        return send_from_directory(
            directory,
            filename,
            as_attachment=True,
            download_name=f"{transcript.audio_file.original_filename.split('.')[0]}_transcript.csv"
        )

    elif format == 'viz':
        # 下載可視化圖表
        if not transcript.visualization_path or not os.path.exists(transcript.visualization_path):
            flash('可視化圖表不存在', 'error')
            return redirect(url_for('audio.view_transcript', transcript_id=transcript.id))

        directory = os.path.dirname(transcript.visualization_path)
        filename = os.path.basename(transcript.visualization_path)

        return send_from_directory(
            directory,
            filename,
            as_attachment=True,
            download_name=f"{transcript.audio_file.original_filename.split('.')[0]}_diarization.png"
        )

    else:
        flash(f'不支援的格式: {format}', 'error')
        return redirect(url_for('audio.view_transcript', transcript_id=transcript.id))


def _format_time(seconds):
    """將秒數格式化為時:分:秒.毫秒格式"""
    if not seconds or not isinstance(seconds, (int, float)):
        return "00:00:00.000"

    m, s = divmod(float(seconds), 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}.{int((float(seconds) % 1) * 1000):03d}"