/**
 * 處理頁面 JavaScript 功能
 */
document.addEventListener('DOMContentLoaded', function() {
    // 獲取元素
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    const statusText = document.getElementById('statusText');
    const actionButtons = document.getElementById('actionButtons');
    const steps = document.querySelectorAll('.step-item');

    // 初始化進度檢查
    window.initProcessMonitor = function(audioId, initialStatus, initialProgress) {
        updateProgress(initialProgress);
        updateStatus(initialStatus);

        // 如果狀態是 pending 或 processing，啟動進度檢查
        if (initialStatus === 'pending' || initialStatus === 'processing') {
            // 開始輪詢處理狀態
            checkProgress(audioId);
        }
    };

    /**
     * 更新進度條
     * @param {number} progress - 進度百分比
     */
    function updateProgress(progress) {
        if (progressBar && progressPercent) {
            progressBar.style.width = progress + '%';
            progressBar.setAttribute('aria-valuenow', progress);
            progressPercent.textContent = Math.round(progress) + '%';
        }
    }

    /**
     * 更新狀態文字
     * @param {string} status - 狀態名稱
     * @param {string} message - 狀態訊息
     */
    function updateStatus(status, message) {
        if (statusText) {
            let statusMsg = '';

            switch (status) {
                case 'pending':
                    statusMsg = '等待處理...';
                    break;
                case 'processing':
                    statusMsg = '處理中...';
                    break;
                case 'completed':
                    statusMsg = '處理完成';
                    break;
                case 'failed':
                    statusMsg = '處理失敗';
                    break;
                default:
                    statusMsg = status;
            }

            if (message) {
                statusMsg += ' - ' + message;
            }

            statusText.textContent = statusMsg;
        }
    }

    /**
     * 更新處理步驟
     * @param {number} currentStep - 當前步驟 (1-5)
     * @param {number} stepProgress - 當前步驟進度 (0-100)
     */
    function updateSteps(currentStep, stepProgress) {
        if (!steps || !steps.length) return;

        // 更新所有步驟狀態
        steps.forEach((step, index) => {
            const stepNum = index + 1;
            const statusDisplay = step.querySelector('.step-status');

            // 清除所有狀態類別
            step.classList.remove('active', 'completed', 'failed');

            if (stepNum < currentStep) {
                // 之前的步驟已完成
                step.classList.add('completed');
                if (statusDisplay) statusDisplay.textContent = '完成';
            } else if (stepNum === currentStep) {
                // 當前步驟
                step.classList.add('active');
                if (statusDisplay) statusDisplay.textContent = `進度: ${stepProgress}%`;
            } else {
                // 後續步驟
                if (statusDisplay) statusDisplay.textContent = '等待中';
            }
        });
    }

    /**
     * 檢查處理進度
     * @param {number} audioId - 音訊檔案 ID
     */
    function checkProgress(audioId) {
        const checkUrl = `/processing_status/${audioId}/check`;

        // 使用 fetch API 檢查進度
        fetch(checkUrl)
            .then(response => response.json())
            .then(data => {
                // 更新進度和狀態
                if (data.progress !== undefined) {
                    updateProgress(data.progress);
                }

                if (data.status) {
                    updateStatus(data.status, data.message);

                    // 根據進度估算當前步驟和步驟進度
                    const progress = data.progress || 0;
                    let currentStep = 1;
                    let stepProgress = 0;

                    if (progress <= 20) {
                        currentStep = 1;
                        stepProgress = progress * 5; // 0-20% = 第一步 0-100%
                    } else if (progress <= 40) {
                        currentStep = 2;
                        stepProgress = (progress - 20) * 5; // 20-40% = 第二步 0-100%
                    } else if (progress <= 60) {
                        currentStep = 3;
                        stepProgress = (progress - 40) * 5; // 40-60% = 第三步 0-100%
                    } else if (progress <= 80) {
                        currentStep = 4;
                        stepProgress = (progress - 60) * 5; // 60-80% = 第四步 0-100%
                    } else {
                        currentStep = 5;
                        stepProgress = (progress - 80) * 5; // 80-100% = 第五步 0-100%
                    }

                    updateSteps(currentStep, Math.round(stepProgress));

                    // 處理完成或失敗
                    if (data.status === 'completed') {
                        // 顯示查看結果按鈕
                        if (actionButtons) {
                            actionButtons.innerHTML = `
                                <a href="${data.redirect_url}" class="btn btn-success">
                                    <i class="fas fa-eye me-2"></i> 查看轉錄結果
                                </a>
                            `;
                        }
                        // 更新所有步驟為完成
                        updateSteps(6, 100);
                    } else if (data.status === 'failed') {
                        // 顯示錯誤訊息
                        if (actionButtons) {
                            actionButtons.innerHTML = `
                                <div class="alert alert-danger">
                                    處理失敗: ${data.message || '發生未知錯誤'}
                                </div>
                                <a href="/upload" class="btn btn-primary">
                                    <i class="fas fa-upload me-2"></i> 重新上傳
                                </a>
                            `;
                        }
                        // 更新步驟狀態
                        steps.forEach((step, index) => {
                            if (index === currentStep - 1) {
                                step.classList.add('failed');
                                const statusDisplay = step.querySelector('.step-status');
                                if (statusDisplay) statusDisplay.textContent = '失敗';
                            }
                        });
                    } else if (data.status === 'processing' || data.status === 'pending') {
                        // 繼續檢查進度
                        setTimeout(() => checkProgress(audioId), 1000);
                    }
                }
            })
            .catch(error => {
                console.error('檢查進度時發生錯誤:', error);
                // 錯誤時也繼續嘗試檢查
                setTimeout(() => checkProgress(audioId), 2000);
            });
    }
});