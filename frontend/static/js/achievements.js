/**
 * CASPER Achievements
 * Загрузка, отображение и уведомления о новых ачивках.
 */

const Achievements = (() => {
  const ICONS = {
    eye:    '👁',
    shield: '🛡',
    zap:    '⚡',
    map:    '🗺',
    star:   '⭐',
    trophy: '🏆',
  };

  /**
   * Загрузить ачивки с сервера и обновить модалку.
   */
  async function load() {
    try {
      const list = await API.get('/api/progress/achievements');
      _render(list);
      return list;
    } catch (e) {
      console.error('[Achievements] Ошибка загрузки:', e);
      return [];
    }
  }

  /**
   * Показать уведомления о новых ачивках после завершения квеста.
   * @param {Array} newAchs — массив из QuestCompleteOut.newly_unlocked_achievements
   */
  async function notifyNew(newAchs) {
    if (!newAchs || newAchs.length === 0) return;
    for (const ach of newAchs) {
      await _showNotification(ach);
      await _sleep(600);
    }
    // Обновляем список в модалке
    await load();
  }

  function _render(list) {
    const container = document.getElementById('achievements-list');
    if (!container) return;

    container.innerHTML = '';
    const unlocked = list.filter(a => a.unlocked);
    const locked   = list.filter(a => !a.unlocked);

    if (unlocked.length === 0 && locked.length === 0) {
      container.innerHTML = '<p style="color:var(--text-secondary);text-align:center;padding:20px">Нет ачивок</p>';
      return;
    }

    // Заголовок
    const header = document.createElement('div');
    header.style.cssText = 'font-size:12px;color:var(--text-secondary);margin-bottom:12px;font-family:var(--font-mono)';
    header.textContent = `РАЗБЛОКИРОВАНО: ${unlocked.length} / ${list.length}`;
    container.appendChild(header);

    [...unlocked, ...locked].forEach(ach => {
      const item = document.createElement('div');
      item.style.cssText = `
        display:flex; align-items:center; gap:12px;
        padding:12px 14px; border-radius:10px;
        border:1px solid ${ach.unlocked ? 'var(--border-bright)' : 'var(--border)'};
        background:${ach.unlocked ? 'rgba(0,170,255,0.06)' : 'transparent'};
        margin-bottom:8px;
        opacity:${ach.unlocked ? '1' : '0.45'};
      `;

      const icon = document.createElement('div');
      icon.style.cssText = 'font-size:28px;width:40px;text-align:center;flex-shrink:0';
      icon.textContent = ICONS[ach.icon] || '🏆';

      const info = document.createElement('div');
      info.style.flex = '1';
      info.innerHTML = `
        <div style="font-size:14px;font-weight:700;color:var(--text-primary);margin-bottom:3px">${ach.title}</div>
        <div style="font-size:12px;color:var(--text-secondary);line-height:1.4">${ach.description}</div>
        ${ach.xp_bonus ? `<div style="font-size:11px;color:var(--success);font-family:var(--font-mono);margin-top:4px;font-weight:700">+${ach.xp_bonus} XP бонус</div>` : ''}
      `;

      const status = document.createElement('div');
      status.style.cssText = 'font-size:18px;flex-shrink:0';
      status.textContent = ach.unlocked ? '✅' : '🔒';

      item.appendChild(icon);
      item.appendChild(info);
      item.appendChild(status);
      container.appendChild(item);
    });
  }

  async function _showNotification(ach) {
    return new Promise(resolve => {
      const popup = document.createElement('div');
      popup.style.cssText = `
        position:fixed; top:80px; right:16px; z-index:200;
        background:var(--bg-panel); border:1px solid var(--success);
        border-radius:14px; padding:14px 18px;
        display:flex; align-items:center; gap:12px;
        box-shadow:0 0 30px rgba(0,255,136,0.3);
        transform:translateX(120%); transition:transform 0.35s cubic-bezier(0.4,0,0.2,1);
        max-width:280px;
      `;
      popup.innerHTML = `
        <div style="font-size:32px">${ICONS[ach.icon] || '🏆'}</div>
        <div>
          <div style="font-size:11px;color:var(--success);font-family:var(--font-mono);letter-spacing:1px;font-weight:700">АЧИВКА РАЗБЛОКИРОВАНА!</div>
          <div style="font-size:14px;font-weight:700;color:var(--text-primary);margin:2px 0">${ach.title}</div>
          ${ach.xp_bonus ? `<div style="font-size:12px;color:var(--success);font-family:var(--font-mono)">+${ach.xp_bonus} XP</div>` : ''}
        </div>
      `;
      document.body.appendChild(popup);

      setTimeout(() => popup.style.transform = 'translateX(0)', 50);
      setTimeout(() => {
        popup.style.transform = 'translateX(120%)';
        setTimeout(() => { popup.remove(); resolve(); }, 400);
      }, 3000);
    });
  }

  function openModal() {
    console.log('[Achievements] openModal вызван');
    const modal = document.getElementById('achievements-modal');
    const inner = document.getElementById('achievements-modal-inner');
    if (!modal) { console.error('[Achievements] modal не найден!'); return; }
    modal.style.opacity = '1';
    modal.style.pointerEvents = 'all';
    if (inner) inner.style.transform = 'translateY(0)';
    load();
  }

  function closeModal() {
    const modal = document.getElementById('achievements-modal');
    const inner = document.getElementById('achievements-modal-inner');
    if (!modal) return;
    modal.style.opacity = '0';
    modal.style.pointerEvents = 'none';
    if (inner) inner.style.transform = 'translateY(100%)';
  }

  function _sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  // Добавляем метод get в API (если нет)
  if (!API.get) {
    API.get = (path) => fetch(path, {
      headers: { 'Authorization': `Bearer ${sessionStorage.getItem('casper_token')}` }
    }).then(r => r.json());
  }

  return { load, notifyNew, openModal, closeModal };
})();
