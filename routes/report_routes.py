"""
報告生成相關路由
處理報告生成、編輯和下載功能
"""
import json
import queue
import time

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, \
    send_from_directory, Response
from flask_login import login_required, current_user
from models.db_models import Report, Transcript, AudioFile, ReportStatus
from processors.report_generator import create_report_generator
from app import db
import os
import datetime
import requests
import logging
from xhtml2pdf import pisa
import markdown

# 創建藍圖
report = Blueprint('report', __name__)

# 設定日誌
logger = logging.getLogger(__name__)


def get_available_ollama_models():
    """
    從 Ollama 伺服器獲取可用的模型列表

    Returns:
        list: 可用模型列表
    """
    default_models = ['無法獲得模型表格']  # 預設模型列表

    try:
        # 獲取 Ollama 伺服器設定
        ollama_host = current_app.config.get('DEFAULT_OLLAMA_HOST', 'localhost')
        ollama_port = current_app.config.get('DEFAULT_OLLAMA_PORT', '11434')

        # 構建請求 URL
        url = f"http://{ollama_host}:{ollama_port}/api/tags"

        # 發送請求
        response = requests.get(url, timeout=3)

        # 檢查回應狀態
        if response.status_code == 200:
            # 解析回應
            data = response.json()
            if 'models' in data:
                # 提取模型名稱
                models = [model['name'] for model in data['models']]
                if models:
                    return models

        logger.warning(f"無法從 Ollama 伺服器獲取模型列表，使用預設值")
        return default_models

    except Exception as e:
        logger.error(f"查詢 Ollama 模型時發生錯誤: {e}")
        return default_models


@report.route('/create/<int:transcript_id>', methods=['GET'])
@login_required
def create_form(transcript_id):
    """顯示報告生成表單"""
    # 檢查轉錄記錄是否存在且屬於當前用戶
    transcript = Transcript.query.join(AudioFile).filter(
        Transcript.id == transcript_id,
        AudioFile.user_id == current_user.id
    ).first_or_404()

    # 獲取 Ollama 模型列表
    ollama_models = get_available_ollama_models()

    # 獲取預設參數
    default_system_prompt = current_app.config.get('DEFAULT_SYSTEM_PROMPT', '')
    default_temperature = current_app.config.get('DEFAULT_TEMPERATURE')
    default_top_p = current_app.config.get('DEFAULT_TOP_P')
    default_top_k = current_app.config.get('DEFAULT_TOP_K')
    default_frequency_penalty = current_app.config.get('DEFAULT_FREQUENCY_PENALTY')
    default_presence_penalty = current_app.config.get('DEFAULT_PRESENCE_PENALTY')
    default_repeat_penalty = current_app.config.get('DEFAULT_REPEAT_PENALTY')

    return render_template(
        'create_report.html',
        transcript=transcript,
        audio_file=transcript.audio_file,
        ollama_models=ollama_models,
        default_ollama_model=current_app.config.get('DEFAULT_OLLAMA_MODEL'),
        default_system_prompt=default_system_prompt,
        default_temperature=default_temperature,
        default_top_p=default_top_p,
        default_top_k=default_top_k,
        default_frequency_penalty=default_frequency_penalty,
        default_presence_penalty=default_presence_penalty,
        default_repeat_penalty=default_repeat_penalty
    )


@report.route('/create/<int:transcript_id>', methods=['POST'])
@login_required
def create_report(transcript_id):
    """處理報告生成請求"""
    # 檢查轉錄記錄是否存在且屬於當前用戶
    transcript = Transcript.query.join(AudioFile).filter(
        Transcript.id == transcript_id,
        AudioFile.user_id == current_user.id
    ).first_or_404()

    # 獲取基本參數
    title = request.form.get('title') or f"會議報告 - {datetime.datetime.now().strftime('%Y-%m-%d')}"
    ollama_model = request.form.get('ollama_model') or current_app.config.get('DEFAULT_OLLAMA_MODEL')
    system_prompt = request.form.get('system_prompt') or current_app.config.get('DEFAULT_SYSTEM_PROMPT')

    # 獲取生成參數
    try:
        temperature = float(request.form.get('temperature')) if request.form.get('temperature') else None
    except ValueError:
        temperature = None

    try:
        top_p = float(request.form.get('top_p')) if request.form.get('top_p') else None
    except ValueError:
        top_p = None

    try:
        top_k = int(request.form.get('top_k')) if request.form.get('top_k') else None
    except ValueError:
        top_k = None

    try:
        frequency_penalty = float(request.form.get('frequency_penalty')) if request.form.get(
            'frequency_penalty') else None
    except ValueError:
        frequency_penalty = None

    try:
        presence_penalty = float(request.form.get('presence_penalty')) if request.form.get('presence_penalty') else None
    except ValueError:
        presence_penalty = None

    try:
        repeat_penalty = float(request.form.get('repeat_penalty')) if request.form.get('repeat_penalty') else None
    except ValueError:
        repeat_penalty = None

    try:
        seed = int(request.form.get('seed')) if request.form.get('seed') else None
    except ValueError:
        seed = None

    # 創建報告記錄
    report_entry = Report(
        title=title,
        system_prompt=system_prompt,
        ollama_model=ollama_model,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        repeat_penalty=repeat_penalty,
        seed=seed,
        status=ReportStatus.GENERATING,
        user_id=current_user.id,
        audio_file_id=transcript.audio_file.id,
        transcript_id=transcript.id
    )

    db.session.add(report_entry)
    db.session.commit()

    # 開始生成報告
    return redirect(url_for('report.generate', report_id=report_entry.id))


@report.route('/generate/<int:report_id>')
@login_required
def generate(report_id):
    """開始生成報告並顯示生成進度頁面"""
    # 檢查報告是否存在且屬於當前用戶
    report_entry = Report.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()

    # 如果狀態為生成中，重定向到生成進度頁面
    if report_entry.status == ReportStatus.GENERATING and report_entry.progress > 0:
        return redirect(url_for('report.generating_status', report_id=report_id))

    # 創建報告生成器
    generator = create_report_generator(report_id)

    # 啟動非同步生成
    generator.generate_async()

    # 重定向到生成進度頁面
    return redirect(url_for('report.generating_status', report_id=report_id))


@report.route('/generating_status/<int:report_id>')
@login_required
def generating_status(report_id):
    """顯示報告生成進度頁面"""
    report_entry = Report.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()
    return render_template('generating.html', report=report_entry)


@report.route('/generating_status/<int:report_id>/check')
@login_required
def check_generating_status(report_id):
    """檢查報告生成進度 (AJAX)"""
    report_entry = Report.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()

    # 檢查生成是否完成
    if report_entry.status == ReportStatus.COMPLETED:
        return jsonify({
            'status': 'completed',
            'progress': 100,
            'message': '報告生成完成',
            'redirect_url': url_for('report.view_report', report_id=report_id)
        })

    # 檢查生成是否失敗
    elif report_entry.status == ReportStatus.FAILED:
        return jsonify({
            'status': 'failed',
            'message': report_entry.error_message,
            'redirect_url': url_for('auth.dashboard')
        })

    # 生成中
    elif report_entry.status == ReportStatus.GENERATING:
        return jsonify({
            'status': 'generating',
            'progress': report_entry.progress,
            'message': f'生成中... {report_entry.progress:.1f}%'
        })

    # 其他狀態
    else:
        return jsonify({
            'status': report_entry.status.value,
            'progress': report_entry.progress
        })


@report.route('/stream/<int:report_id>')
@login_required
def stream_report(report_id):
    """
    使用 Server-Sent Events (SSE) 串流獲取報告生成內容
    這個端點用於建立持久連接，實時推送 LLM 生成的內容到前端
    """
    # 檢查報告是否存在且屬於當前用戶
    report_entry = Report.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()

    # 創建報告生成器 (但不啟動生成)
    app = current_app._get_current_object()  # 獲取實際的應用對象，避免上下文問題
    generator = create_report_generator(report_id)

    def generate_events():
        """生成 SSE 事件，優化版本一次取出所有剩餘訊息"""
        # 使用應用上下文
        with app.app_context():
            while True:
                try:
                    # 檢查報告狀態，若已完成或失敗則退出
                    current_report = Report.query.get(report_id)
                    if current_report.status == ReportStatus.COMPLETED:
                        # 如果報告已完成生成，發送結束事件
                        yield "event: done\ndata: done\n\n"
                        break
                    elif current_report.status == ReportStatus.FAILED:
                        # 如果報告生成失敗，發送錯誤事件
                        yield f"event: error\ndata: {current_report.error_message or '未知錯誤'}\n\n"
                        break

                    # 一次性取出所有目前可用的訊息
                    messages = []
                    try:
                        # 取出訊息隊列中所有可用訊息
                        queue_to_use = getattr(current_app, f"report_queue_{report_id}", None)
                        if queue_to_use is None:
                            logger.warning(f"找不到報告 {report_id} 的訊息隊列")
                            queue_to_use = generator.message_queue

                        # 嘗試從隊列獲取所有可用訊息
                        while True:
                            try:
                                message = queue_to_use.get(block=False)
                                if message:
                                    messages.append(message)
                            except queue.Empty:
                                break
                    except Exception as queue_err:
                        logger.error(f"從隊列獲取訊息時出錯: {queue_err}")

                    # 如果有取得訊息，則批次發送
                    if messages:
                        combined_message = ''.join(messages)
                        logger.info(f"發送內容片段：長度 {len(combined_message)} 字符")
                        yield f"data: {json.dumps({'chunk': combined_message})}\n\n"
                    else:
                        # 保持連接活躍
                        yield f"data: {json.dumps({'heartbeat': True})}\n\n"

                    # 短暫暫停，避免過於頻繁的檢查
                    time.sleep(0.2)

                except Exception as e:
                    logger.error(f"生成事件時發生錯誤: {e}")
                    yield f"event: error\ndata: 生成事件時發生錯誤: {str(e)}\n\n"
                    break

    # 返回串流響應
    return Response(generate_events(), mimetype='text/event-stream')


@report.route('/reports')
@login_required
def list_reports():
    """列出用戶的所有報告"""
    reports = Report.query.filter_by(user_id=current_user.id).all()
    return render_template('reports_list.html', reports=reports)


@report.route('/report/<int:report_id>')
@login_required
def view_report(report_id):
    """查看報告"""
    report_entry = Report.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()

    # 讀取報告內容
    markdown_content = ""
    if report_entry.markdown_path and os.path.exists(report_entry.markdown_path):
        with open(report_entry.markdown_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()

    return render_template(
        'report.html',
        report=report_entry,
        audio_file=report_entry.audio_file,
        transcript=report_entry.transcript,
        markdown_content=markdown_content,
        has_pdf=report_entry.pdf_path and os.path.exists(report_entry.pdf_path)
    )


@report.route('/report/<int:report_id>/edit', methods=['GET'])
@login_required
def edit_report(report_id):
    """編輯報告頁面"""
    report_entry = Report.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()

    # 讀取報告內容
    markdown_content = ""
    if report_entry.markdown_path and os.path.exists(report_entry.markdown_path):
        with open(report_entry.markdown_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()

    return render_template(
        'edit_report.html',
        report=report_entry,
        audio_file=report_entry.audio_file,
        transcript=report_entry.transcript,
        markdown_content=markdown_content
    )


@report.route('/report/<int:report_id>/edit', methods=['POST'])
@login_required
def save_report(report_id):
    """保存編輯後的報告"""
    report_entry = Report.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()

    try:
        # 獲取編輯後的內容
        markdown_content = request.form.get('markdown_content')

        if not markdown_content:
            flash('報告內容不能為空', 'error')
            return redirect(url_for('report.edit_report', report_id=report_id))

        # 從原始路徑中提取上傳 ID
        upload_id = os.path.basename(os.path.dirname(report_entry.markdown_path)) if report_entry.markdown_path else None

        # 如果沒有上傳 ID (可能是舊報告)，則從轉錄路徑獲取
        if not upload_id and report_entry.transcript and report_entry.transcript.csv_path:
            upload_id = os.path.basename(os.path.dirname(report_entry.transcript.csv_path))

        # 確定報告目錄
        report_dir = os.path.join(current_app.config['REPORT_FOLDER'], upload_id) if upload_id else current_app.config['REPORT_FOLDER']
        os.makedirs(report_dir, exist_ok=True)

        # 保存編輯後的內容
        edited_basename = f"report_{report_id}_edited_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        edited_path = os.path.join(report_dir, f"{edited_basename}.md")

        with open(edited_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        # 更新報告記錄
        report_entry.markdown_path = edited_path
        report_entry.updated_at = datetime.datetime.now()
        db.session.commit()

        # 嘗試重新生成 PDF (如果支援)
        try:
            # 設定 PDF 輸出路徑
            edited_pdf_path = os.path.join(report_dir, f"{edited_basename}.pdf")

            # 使用 xhtml2pdf 生成 PDF
            try:
                # 將 Markdown 轉換為 HTML
                html_content = markdown.markdown(markdown_content)

                # 添加基本的 CSS 樣式
                styled_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>{report_entry.title}</title>
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
                with open(edited_pdf_path, "w+b") as result_file:
                    pdf_status = pisa.CreatePDF(styled_html, dest=result_file)

                if not pdf_status.err:
                    # 更新 PDF 路徑
                    report_entry.pdf_path = edited_pdf_path
                    db.session.commit()
                    logger.info(f"已儲存 PDF 報告到: {edited_pdf_path}")
                else:
                    logger.error(f"生成 PDF 時發生錯誤: {pdf_status.err}")

            except ImportError:
                logger.warning("未找到 xhtml2pdf 套件，無法生成 PDF 報告")

        except Exception as e:
            flash(f'重新生成 PDF 時發生錯誤: {e}', 'warning')
            logger.error(f"生成 PDF 報告時發生錯誤: {e}")

        flash('報告已成功保存', 'success')
        return redirect(url_for('report.view_report', report_id=report_id))

    except Exception as e:
        flash(f'保存報告時發生錯誤: {e}', 'error')
        return redirect(url_for('report.edit_report', report_id=report_id))


@report.route('/report/<int:report_id>/download/<format>')
@login_required
def download_report(report_id, format):
    """下載報告"""
    report_entry = Report.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()

    if format == 'md' or format == 'markdown':
        # 下載 Markdown 檔案
        if not report_entry.markdown_path or not os.path.exists(report_entry.markdown_path):
            flash('報告 Markdown 檔案不存在', 'error')
            return redirect(url_for('report.view_report', report_id=report_id))

        directory = os.path.dirname(report_entry.markdown_path)
        filename = os.path.basename(report_entry.markdown_path)

        return send_from_directory(
            directory,
            filename,
            as_attachment=True,
            download_name=f"{report_entry.title.replace(' ', '_')}.md"
        )

    elif format == 'pdf':
        # 下載 PDF 檔案
        if not report_entry.pdf_path or not os.path.exists(report_entry.pdf_path):
            flash('報告 PDF 檔案不存在', 'error')
            return redirect(url_for('report.view_report', report_id=report_id))

        directory = os.path.dirname(report_entry.pdf_path)
        filename = os.path.basename(report_entry.pdf_path)

        return send_from_directory(
            directory,
            filename,
            as_attachment=True,
            download_name=f"{report_entry.title.replace(' ', '_')}.pdf"
        )

    else:
        flash(f'不支援的格式: {format}', 'error')
        return redirect(url_for('report.view_report', report_id=report_id))


@report.route('/report/<int:report_id>/regenerate', methods=['POST'])
@login_required
def regenerate_report(report_id):
    """使用現有參數重新生成報告"""
    report_entry = Report.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()

    # 重置報告狀態
    report_entry.status = ReportStatus.GENERATING
    report_entry.progress = 0
    report_entry.error_message = None
    db.session.commit()

    # 開始重新生成
    return redirect(url_for('report.generate', report_id=report_id))


