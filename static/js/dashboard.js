/**
 * 儀表板頁面 JavaScript 功能
 */
document.addEventListener('DOMContentLoaded', function() {
    // 統計數字動畫
    const statsNumbers = document.querySelectorAll('.stats-number');

    statsNumbers.forEach(function(element) {
        const finalValue = parseInt(element.textContent);
        animateNumber(element, 0, finalValue, 1500);
    });

    // 初始化工具提示
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // 設定狀態徽章顏色
    setupStatusBadges();
});

/**
 * 設定狀態徽章的類別和顏色
 */
function setupStatusBadges() {
    const statusBadges = document.querySelectorAll('.status-badge');

    statusBadges.forEach(function(badge) {
        // 已經有狀態類別的跳過
        if (badge.classList.contains('status-pending') ||
            badge.classList.contains('status-processing') ||
            badge.classList.contains('status-completed') ||
            badge.classList.contains('status-failed') ||
            badge.classList.contains('status-generating')) {
            return;
        }

        const status = badge.textContent.trim().toLowerCase();

        switch (status) {
            case 'pending':
                badge.classList.add('status-pending');
                break;
            case 'processing':
                badge.classList.add('status-processing');
                break;
            case 'completed':
                badge.classList.add('status-completed');
                break;
            case 'failed':
                badge.classList.add('status-failed');
                break;
            case 'generating':
                badge.classList.add('status-generating');
                break;
            case 'canceled':
                badge.classList.add('status-pending');
                break;
            default:
                badge.classList.add('status-pending');
        }
    });
}

/**
 * 數字動畫函數
 * @param {HTMLElement} element - 要動畫的元素
 * @param {Number} start - 起始值
 * @param {Number} end - 結束值
 * @param {Number} duration - 動畫持續時間 (毫秒)
 */
function animateNumber(element, start, end, duration) {
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const value = Math.floor(progress * (end - start) + start);
        element.textContent = value;
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

/**
 * 獲取最近的音訊檔案和報告
 * 這裡可以擴展為動態載入更多資料的功能
 */
function loadRecentItems() {
    // 如果需要從服務器動態獲取更多數據，可以在這裡實現
    // 例如，使用 AJAX 請求獲取更多音訊檔案或報告
    console.log('可以在這裡實現動態加載更多數據的功能');
}