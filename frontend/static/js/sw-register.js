/**
 * Регистрация Service Worker.
 * Подключается на всех страницах FirstShift.
 */

(function registerSW() {
  if (!('serviceWorker' in navigator)) {
    console.info('[SW] Service Worker не поддерживается этим браузером');
    return;
  }

  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then(reg => {
        console.log('[SW] Зарегистрирован, scope:', reg.scope);

        // Слушаем сообщения от SW (например о синхронизации Safety Check)
        navigator.serviceWorker.addEventListener('message', event => {
          if (event.data?.type === 'safety_check_synced') {
            console.log('[SW] Safety Check синхронизирован:', event.data.client_id);
            // Можно показать тост пользователю если он на странице safety
            const toast = document.createElement('div');
            toast.style.cssText = `
              position:fixed; bottom:80px; left:50%;
              transform:translateX(-50%);
              background:rgba(0,255,136,0.15);
              border:1px solid #00ff88; border-radius:12px;
              padding:10px 18px; font-size:13px; color:#00ff88;
              font-weight:600; z-index:999; pointer-events:none;
              animation:fadeInOut 3s ease forwards;
            `;
            toast.textContent = '✅ Safety Check синхронизирован';
            if (!document.getElementById('sw-toast-style')) {
              const s = document.createElement('style');
              s.id = 'sw-toast-style';
              s.textContent = `
                @keyframes fadeInOut {
                  0%   { opacity:0; transform:translateX(-50%) translateY(10px); }
                  15%  { opacity:1; transform:translateX(-50%) translateY(0); }
                  80%  { opacity:1; }
                  100% { opacity:0; transform:translateX(-50%) translateY(-6px); }
                }
              `;
              document.head.appendChild(s);
            }
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
          }
        });
      })
      .catch(err => console.error('[SW] Ошибка регистрации:', err));
  });
})();
