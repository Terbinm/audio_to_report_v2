"""
報告生成相關路由
處理報告生成、編輯和下載功能
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, \
    send_from_directory
from flask_login import login_required, current_user
from models.db_models import Report, Transcript, AudioFile, ReportStatus
from processors.report_generator import create_report_generator
from app import db
import os
import json
import datetime
import requests
import logging

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
    default_models = ['phi4:14b', 'llama3', 'gemma:7b', 'mistral', 'qwen:14b']  # 預設模型列表

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

    # 獲取預設提示詞
    default_system_prompt = current_app.config.get('DEFAULT_SYSTEM_PROMPT', '')

    return render_template(
        'create_report.html',
        transcript=transcript,
        audio_file=transcript.audio_file,
        ollama_models=ollama_models,
        default_ollama_model=current_app.config.get('DEFAULT_OLLAMA_MODEL'),
        default_system_prompt=default_system_prompt
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

    # 獲取參數
    title = request.form.get('title') or f"會議報告 - {datetime.datetime.now().strftime('%Y-%m-%d')}"
    ollama_model = request.form.get('ollama_model') or current_app.config.get('DEFAULT_OLLAMA_MODEL')
    system_prompt = request.form.get('system_prompt') or current_app.config.get('DEFAULT_SYSTEM_PROMPT')

    # 創建報告記錄
    report_entry = Report(
        title=title,
        system_prompt=system_prompt,
        ollama_model=ollama_model,
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
    """串流獲取報告生成內容 (用於 SSE)"""
    # 這個函數實際上只返回一個靜態 JSON
    # 實際的串流處理在前端通過 WebSocket 或 Server-Sent Events 實現
    report_entry = Report.query.filter_by(id=report_id, user_id=current_user.id).first_or_404()

    # 創建報告生成器 (但不啟動生成)
    generator = create_report_generator(report_id)

    # 嘗試獲取一條訊息
    message = generator.get_messages(timeout=0.1)

    if message:
        return jsonify({
            'status': 'ok',
            'chunk': message
        })
    else:
        return jsonify({
            'status': 'empty',
            'chunk': ''
        })


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

        # 保存編輯後的內容
        edited_path = report_entry.markdown_path.replace('.md', '_edited.md')

        with open(edited_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        # 更新報告記錄
        report_entry.markdown_path = edited_path
        report_entry.updated_at = datetime.datetime.utcnow()
        db.session.commit()

        # 嘗試重新生成 PDF (如果支援)
        try:
            if report_entry.pdf_path:
                edited_pdf_path = report_entry.pdf_path.replace('.pdf', '_edited.pdf')

                # 嘗試使用 weasyprint 重新生成 PDF
                try:
                    from weasyprint import HTML
                    import markdown

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
                            @page {{ size: A4; margin: 2cm; }}
                        </style>
                    </head>
                    <body>
                        {html_content}
                    </body>
                    </html>
                    """

                    # 生成 PDF
                    HTML(string=styled_html).write_pdf(edited_pdf_path)

                    # 更新 PDF 路徑
                    report_entry.pdf_path = edited_pdf_path
                    db.session.commit()

                except ImportError:
                    logger.warning("未找到 weasyprint 套件，無法重新生成 PDF")

        except Exception as e:
            flash(f'重新生成 PDF 時發生錯誤: {e}', 'warning')

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