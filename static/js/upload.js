/**
 * 上傳頁面 JavaScript 功能
 */
document.addEventListener('DOMContentLoaded', function() {
    // 獲取 DOM 元素
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('audio_file');
    const selectedFile = document.querySelector('.selected-file');
    const fileName = document.querySelector('.file-name');
    const fileSize = document.querySelector('.file-size');
    const removeFileBtn = document.querySelector('.remove-file');
    const submitBtn = document.getElementById('submitBtn');
    const speakerOption = document.querySelectorAll('input[name="speaker_option"]');
    const speakerAutoOptions = document.querySelector('.speaker-auto-options');
    const speakerFixedOptions = document.querySelector('.speaker-fixed-options');

    // 拖放區域事件
    if (dropZone) {
        // 拖放事件處理
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        // 拖放視覺反饋
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, function() {
                dropZone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, function() {
                dropZone.classList.remove('dragover');
            }, false);
        });

        // 處理檔案拖放
        dropZone.addEventListener('drop', function(e) {
            const dt = e.dataTransfer;
            const files = dt.files;

            if (files.length) {
                fileInput.files = files;
                handleFileSelect();
            }
        }, false);

        // 點擊上傳區域觸發文件選擇
        dropZone.addEventListener('click', function() {
            fileInput.click();
        });
    }

    // 文件選擇事件
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
    }

    // 移除選擇的檔案
    if (removeFileBtn) {
        removeFileBtn.addEventListener('click', function() {
            fileInput.value = '';
            selectedFile.style.display = 'none';
            submitBtn.disabled = true;
        });
    }

    // 說話者選項切換
    if (speakerOption.length) {
        speakerOption.forEach(function(option) {
            option.addEventListener('change', function() {
                if (this.value === 'auto') {
                    speakerAutoOptions.style.display = 'block';
                    speakerFixedOptions.style.display = 'none';
                } else {
                    speakerAutoOptions.style.display = 'none';
                    speakerFixedOptions.style.display = 'block';
                }
            });
        });
    }

    // 處理文件選擇
    function handleFileSelect() {
        if (fileInput.files.length) {
            const file = fileInput.files[0];

            // 檢查檔案類型
            const allowedExtensions = getExtensions();
            const fileExtension = file.name.split('.').pop().toLowerCase();

            if (!allowedExtensions.includes(fileExtension)) {
                alert('不支援的檔案類型！支援的格式：' + allowedExtensions.join(', '));
                fileInput.value = '';
                return;
            }

            // 檢查檔案大小
            const maxSize = getMaxFileSize();
            if (file.size > maxSize) {
                alert('檔案太大！最大允許大小：' + formatFileSize(maxSize));
                fileInput.value = '';
                return;
            }

            // 顯示選擇的檔案
            fileName.textContent = file.name;
            fileSize.textContent = formatFileSize(file.size);
            selectedFile.style.display = 'block';
            submitBtn.disabled = false;
        } else {
            selectedFile.style.display = 'none';
            submitBtn.disabled = true;
        }
    }

    // 獲取允許的副檔名
    function getExtensions() {
        // 從頁面獲取或使用預設值
        const fileInput = document.getElementById('audio_file');
        const accept = fileInput.getAttribute('accept');

        if (accept) {
            return accept.split(',').map(ext => ext.replace('.', ''));
        }

        return ['wav', 'mp3', 'ogg', 'flac', 'm4a'];
    }

    // 獲取最大文件大小
    function getMaxFileSize() {
        // 從頁面獲取或使用預設值（100MB）
        return 100 * 1024 * 1024;
    }

    // 格式化檔案大小
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // 表單提交前檢查
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            if (!fileInput.files.length) {
                e.preventDefault();
                alert('請選擇一個音訊檔案！');
                return false;
            }

            // 顯示上傳進度條
            if (selectedFile) {
                const progressBar = selectedFile.querySelector('.progress');
                const progressBarInner = progressBar.querySelector('.progress-bar');

                progressBar.style.display = 'block';

                // 模擬上傳進度
                let progress = 0;
                const interval = setInterval(function() {
                    progress += 5;
                    progressBarInner.style.width = progress + '%';
                    progressBarInner.setAttribute('aria-valuenow', progress);

                    if (progress >= 100) {
                        clearInterval(interval);
                    }
                }, 100);
            }

            // 禁用提交按鈕，防止重複提交
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> 上傳中...';
        });
    }
});