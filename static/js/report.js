/**
 * 報告頁面 JavaScript 功能
 */
document.addEventListener('DOMContentLoaded', function() {
    // 初始化 Markdown 渲染
    setupMarkdown();

    // 初始化確認對話框
    setupConfirmDialogs();

    // 初始化複製按鈕
    setupCopyButtons();

    // 初始化工具提示
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

/**
 * 設定 Markdown 渲染
 */
function setupMarkdown() {
    // 如果已經在服務端渲染了 Markdown，這裡就不需要額外處理
    // 但如果需要在客戶端渲染，可以使用 marked.js 等庫

    // 為 Markdown 內容中的表格添加 Bootstrap 類別
    const markdownBody = document.querySelector('.markdown-body');
    if (markdownBody) {
        const tables = markdownBody.querySelectorAll('table');
        tables.forEach(function(table) {
            table.classList.add('table', 'table-bordered', 'table-striped', 'table-hover');
        });

        // 為 Markdown 內容中的圖片添加響應式類別
        const images = markdownBody.querySelectorAll('img');
        images.forEach(function(img) {
            img.classList.add('img-fluid');
        });

        // 為標題添加錨點和鏈接
        const headings = markdownBody.querySelectorAll('h1, h2, h3, h4, h5, h6');
        headings.forEach(function(heading) {
            // 創建 ID (將標題文字轉為 kebab-case)
            const id = heading.textContent
                .toLowerCase()
                .replace(/[^\w\s-]/g, '')  // 移除非單詞字符
                .replace(/\s+/g, '-')      // 將空格替換為連字符
                .replace(/--+/g, '-');     // 替換多個連字符為單個連字符

            heading.id = id;

            // 添加可點擊的鏈接
            const link = document.createElement('a');
            link.classList.add('heading-link');
            link.href = `#${id}`;
            link.innerHTML = '<i class="fas fa-link fa-xs text-muted ms-2"></i>';
            link.style.textDecoration = 'none';
            link.style.opacity = '0';
            link.style.transition = 'opacity 0.2s';

            heading.appendChild(link);

            // 滑鼠懸停時顯示鏈接
            heading.addEventListener('mouseenter', function() {
                link.style.opacity = '1';
            });

            heading.addEventListener('mouseleave', function() {
                link.style.opacity = '0';
            });
        });
    }
}

/**
 * 設定確認對話框
 */
function setupConfirmDialogs() {
    document.querySelectorAll('[data-confirm]').forEach(function(element) {
        element.addEventListener('click', function(e) {
            if (!confirm(this.getAttribute('data-confirm') || '確定要執行此操作？')) {
                e.preventDefault();
                return false;
            }
        });
    });
}

/**
 * 設定複製按鈕
 */
function setupCopyButtons() {
    // 為每個代碼塊添加複製按鈕
    const codeBlocks = document.querySelectorAll('pre code');
    codeBlocks.forEach(function(codeBlock, index) {
        // 創建按鈕容器
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'copy-button-container';
        buttonContainer.style.position = 'absolute';
        buttonContainer.style.top = '5px';
        buttonContainer.style.right = '5px';

        // 創建複製按鈕
        const copyButton = document.createElement('button');
        copyButton.type = 'button';
        copyButton.className = 'btn btn-sm btn-outline-light copy-button';
        copyButton.innerHTML = '<i class="fas fa-copy"></i>';
        copyButton.title = '複製代碼';
        copyButton.dataset.bsToggle = 'tooltip';
        copyButton.dataset.bsPlacement = 'top';

        // 添加複製功能
        copyButton.addEventListener('click', function() {
            const code = codeBlock.textContent;
            copyToClipboard(code);

            // 顯示複製成功
            copyButton.innerHTML = '<i class="fas fa-check"></i>';
            setTimeout(function() {
                copyButton.innerHTML = '<i class="fas fa-copy"></i>';
            }, 2000);
        });

        // 將按鈕添加到容器
        buttonContainer.appendChild(copyButton);

        // 設置代碼塊為相對定位
        const parentPre = codeBlock.parentElement;
        parentPre.style.position = 'relative';

        // 將按鈕容器添加到代碼塊
        parentPre.appendChild(buttonContainer);
    });
}

/**
 * 複製文本到剪貼板
 * @param {string} text - 要複製的文本
 */
function copyToClipboard(text) {
    // 使用新的 Clipboard API
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text)
            .catch(err => console.error('無法複製文本：', err));
    } else {
        // 舊方法作為備份
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
    }
}