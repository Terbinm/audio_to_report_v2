
/**
 * 認證頁面相關 JavaScript 功能
 */
document.addEventListener('DOMContentLoaded', function() {
    // 獲取註冊表單
    const registerForm = document.getElementById('registerForm');

    // 如果註冊表單存在，添加驗證
    if (registerForm) {
        registerForm.addEventListener('submit', function(e) {
            // 獲取密碼字段
            const password = document.getElementById('password');
            const passwordConfirm = document.getElementById('password_confirm');

            // 驗證密碼長度
            if (password.value.length < 6) {
                e.preventDefault();
                alert('密碼長度必須至少 6 個字元');
                password.focus();
                return false;
            }

            // 驗證密碼匹配
            if (password.value !== passwordConfirm.value) {
                e.preventDefault();
                alert('兩次輸入的密碼不一致');
                passwordConfirm.focus();
                return false;
            }
        });
    }

    // 密碼欄位顯示/隱藏功能可以在這裡添加
});