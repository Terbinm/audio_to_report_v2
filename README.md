## 系統架構

```
                  +------------------------+
                  |                        |
                  |  網頁介面 (Flask App)   |
                  |                        |
                  +-----------+------------+
                              |
                              |
              +---------------v---------------+
              |                               |
+-------------+-------------+  +--------------+----------------+
|                           |  |                               |
| 音訊處理模組               |  | 報告生成模組                   |
| (AudioProcessor)          |  | (ReportGenerator)            |
|                           |  |                               |
| - Whisper轉錄              |  | - 轉錄後處理                   |
| - 說話者分割 (Diarization)  |  | - LLM報告生成                  |
| - 可視化                   |  | - 報告渲染                     |
|                           |  |                               |
+---------------------------+  +-------------------------------+
```

## 資料夾結構

```
audio_to_report/
├── app.py              # 主應用程式 (Flask 應用入口)X
├── config.py           # 配置文件 (已提供)X
├── auth.py             # 使用者認證模組X
├── models/X
│   ├── __init__.pyX
│   ├── db_models.py    # 資料庫模型X
│   └── user.py         # 使用者模型X
├── processors/X
│   ├── __init__.pyX
│   ├── audio_processor.py    # 音訊處理器 (基於wav_to_transcript.py)X
│   └── report_generator.py   # 報告生成器X
├── routes/X
│   ├── __init__.pyX
│   ├── auth_routes.py      # 認證相關路由X
│   ├── audio_routes.py     # 音訊處理相關路由X
│   └── report_routes.py    # 報告生成相關路由X
├── static/
│   ├── css/            # CSS 樣式
│   ├── js/             # JavaScript 檔案
│   ├── images/         # 圖片
│   └── outputs/        # 輸出的可視化圖表 (為網頁顯示)
├── templates/
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html
│   ├── dashboard.html  # 儀表板頁面
│   ├── base.html  # 模板頁面
│   ├── upload.html     # 上傳頁面
│   ├── process.html    # 處理頁面
│   └── report.html     # 報告頁面
├── uploads/            # 上傳的音訊檔案
├── outputs/
│   ├── transcripts/    # 轉錄結果
│   ├── visualizations/ # 可視化結果
│   └── reports/        # 生成的報告
├── utils/X
│   ├── __init__.pyX
│   ├── file_utils.py   # 檔案處理工具X
│   └── stream_helpers.py # 串流處理工具X
├── requirements.txt    # 相依套件X
└── README.md           # 說明文件X
```

## 核心功能模組

### 1. 音訊處理模組 (AudioProcessor)
- 基於 `wav_to_transcript.py` 的功能
- 使用 Whisper 進行語音轉文字
- 使用 Pyannote 進行說話者分割
- 產生轉錄文件與可視化圖表

### 2. 報告生成模組 (ReportGenerator)
- 處理轉錄結果
- 連接到 LLM (使用 Ollama)
- 生成會議報告
- 支援即時報告生成與轉錄編輯

### 3. Web 應用模組 (Flask App)
- 使用者認證與管理
- 檔案上傳與處理
- 轉錄結果展示與編輯
- 報告生成與下載
- WebSocket 支援即時進度更新

## 使用者流程

1. **登入/註冊**：使用者需先登入系統
2. **上傳**：上傳音訊檔案
3. **處理**：系統自動處理音訊，轉錄文字並分割說話者
4. **審核**：使用者審核並可編輯轉錄結果
5. **生成**：系統使用 LLM 生成會議報告
6. **下載**：使用者可下載最終報告 (Markdown 或 PDF 格式)

## 技術堆疊

- **後端**：Flask, SQLAlchemy
- **前端**：HTML, CSS, JavaScript, Bootstrap
- **資料庫**：SQLite (可擴展至 PostgreSQL)
- **音訊處理**：Whisper, Pyannote, Librosa
- **報告生成**：Ollama LLM
- **即時更新**：Flask-SocketIO