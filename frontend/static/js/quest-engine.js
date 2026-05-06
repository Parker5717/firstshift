/**
 * FirstShift Quest Engine
 * Управляет состоянием квестов и ачивок в единой модалке.
 */

const QuestEngine = (() => {
  let _quests = [];
  let _activeQuest = null;
  let _activeTab = 'quests'; // 'quests' | 'achievements'
  let _regulation = false;

  const ICONS = {
    discovery: '🔍',
    safety:    '🦺',
    knowledge: '📚',
    speed_run: '⚡',
  };

  const STATUS_LABELS = {
    available: 'Доступен',
    active:    'Активен',
    completed: 'Выполнен',
    locked:    'Заблокирован',
    failed:    'Провален',
  };

  const ACH_ICONS = {
    eye: '👁', shield: '🛡', zap: '⚡',
    map: '🗺', star: '⭐', trophy: '🏆',
  };

  // ── Режим «Регламент» — без геймификации ────────────────────
  function setRegulationMode() {
    _regulation = true;
    const achTab = document.getElementById('qtab-achievements');
    if (achTab) achTab.style.display = 'none';
    const questsTab = document.getElementById('qtab-quests');
    if (questsTab) questsTab.textContent = 'Задачи';
  }

  // ── Загрузка ────────────────────────────────────────────────
  async function load() {
    try {
      const data = await API.getQuests();
      _quests = data.quests || [];
      _activeQuest = _quests.find(q => q.status === 'active') || null;
      _renderQuestList();
      _renderActiveCard();
      return _quests;
    } catch (err) {
      console.error('[QuestEngine] Ошибка загрузки квестов:', err);
      return [];
    }
  }

  // ── Старт квеста ─────────────────────────────────────────────
  async function start(slug) {
    try {
      await API.startQuest(slug);
      if (!_regulation && typeof Mascot !== 'undefined') Mascot.onQuestStart();
      await load();
      const quest = _quests.find(q => q.slug === slug);
      if (quest?.type === 'speed_run' && typeof SpeedRun !== 'undefined') {
        SpeedRun.start(quest);
      }
      return true;
    } catch (err) {
      if (typeof Mascot !== 'undefined') Mascot.onError();
      alert(`Не удалось начать квест: ${err.message}`);
      return false;
    }
  }

  // ── Завершение квеста ────────────────────────────────────────
  async function complete(slug) {
    try {
      const result = await API.completeQuest(slug);
      if (typeof SpeedRun !== 'undefined') SpeedRun.stop();
      if (!_regulation) {
        XPBar.showXPGain(result.xp_gained, result.leveled_up, result.new_level, result.message);
        AROverlay.flashSuccess();
        if (typeof Mascot !== 'undefined') {
          if (result.leveled_up) Mascot.onLevelUp();
          else Mascot.onQuestComplete();
        }
        if (result.newly_unlocked_achievements?.length > 0) {
          setTimeout(() => _notifyAchievements(result.newly_unlocked_achievements), 1500);
        }
      }
      await load();
      return result;
    } catch (err) {
      if (typeof Mascot !== 'undefined') Mascot.onError();
      console.error('[QuestEngine] Ошибка завершения квеста:', err);
      return null;
    }
  }

  function getActive() { return _activeQuest; }
  function getAll()    { return _quests; }

  // ── Рендер списка квестов ─────────────────────────────────────
  function _renderQuestList() {
    const list = document.getElementById('quest-list-panel');
    if (!list) return;
    list.innerHTML = '';

    _quests.forEach(q => {
      const item = document.createElement('div');
      item.className = `quest-item ${q.status}`;

      if (_regulation) {
        const checkIcon = q.status === 'completed' ? '✅'
                        : q.status === 'active'    ? '▶'
                        : q.status === 'locked'    ? '🔒' : '⬜';
        item.innerHTML = `
          <div class="quest-item-icon">${checkIcon}</div>
          <div class="quest-item-info" style="flex:1">
            <div class="quest-item-title">${q.title}</div>
            <div style="font-size:12px;color:var(--text-secondary);margin-top:2px;line-height:1.4">${q.description || ''}</div>
          </div>
          <span class="badge badge-${q.status}" style="flex-shrink:0">${STATUS_LABELS[q.status] || q.status}</span>
        `;
      } else {
        item.innerHTML = `
          <div class="quest-item-icon">${ICONS[q.type] || '🎯'}</div>
          <div class="quest-item-info">
            <div class="quest-item-title">${q.title}</div>
            <div class="quest-item-xp">+${q.xp_reward} XP</div>
          </div>
          <span class="badge badge-${q.status}">${STATUS_LABELS[q.status] || q.status}</span>
        `;
      }

      if (q.status === 'available') {
        item.addEventListener('click', async () => {
          const prompt = _regulation
            ? `Начать задачу «${q.title}»?\n\n${q.description}`
            : `Начать квест «${q.title}»?\n\n${q.description}`;
          if (confirm(prompt)) {
            await start(q.slug);
            closeModal();
          }
        });
      } else if (q.status === 'active') {
        item.addEventListener('click', () => closeModal());
      }

      list.appendChild(item);
    });
  }

  // ── Рендер ачивок ────────────────────────────────────────────
  async function _renderAchievements() {
    const panel = document.getElementById('achievements-list-panel');
    if (!panel) return;
    panel.innerHTML = '<div style="color:var(--text-dim);text-align:center;padding:20px;font-size:13px">Загрузка...</div>';

    try {
      const list = await API.get('/api/progress/achievements');
      panel.innerHTML = '';

      const unlocked = list.filter(a => a.unlocked);
      const locked   = list.filter(a => !a.unlocked);

      // Счётчик
      const counter = document.createElement('div');
      counter.style.cssText = 'font-size:12px;color:var(--text-secondary);margin-bottom:12px;font-family:var(--font-mono);padding:0 2px';
      counter.textContent = `РАЗБЛОКИРОВАНО: ${unlocked.length} / ${list.length}`;
      panel.appendChild(counter);

      [...unlocked, ...locked].forEach(ach => {
        const item = document.createElement('div');
        item.style.cssText = `
          display:flex; align-items:center; gap:12px;
          padding:12px 14px; border-radius:12px; margin-bottom:8px;
          border:1px solid ${ach.unlocked ? 'rgba(0,170,255,0.3)' : 'var(--border)'};
          background:${ach.unlocked ? 'rgba(0,170,255,0.06)' : 'transparent'};
          opacity:${ach.unlocked ? '1' : '0.4'};
        `;
        item.innerHTML = `
          <div style="font-size:28px;width:40px;text-align:center;flex-shrink:0">${ACH_ICONS[ach.icon] || '🏆'}</div>
          <div style="flex:1">
            <div style="font-size:14px;font-weight:700;color:var(--text-primary);margin-bottom:3px">${ach.title}</div>
            <div style="font-size:12px;color:var(--text-secondary);line-height:1.4">${ach.description}</div>
            ${ach.xp_bonus ? `<div style="font-size:11px;color:var(--success);font-family:var(--font-mono);margin-top:3px;font-weight:700">+${ach.xp_bonus} XP бонус</div>` : ''}
          </div>
          <div style="font-size:18px;flex-shrink:0">${ach.unlocked ? '✅' : '🔒'}</div>
        `;
        panel.appendChild(item);
      });
    } catch (e) {
      panel.innerHTML = '<div style="color:var(--danger);text-align:center;padding:20px;font-size:13px">Ошибка загрузки ачивок</div>';
    }
  }

  // ── Уведомление о новых ачивках ──────────────────────────────
  async function _notifyAchievements(newAchs) {
    for (const ach of newAchs) {
      await _showAchNotification(ach);
      await new Promise(r => setTimeout(r, 600));
    }
  }

  function _showAchNotification(ach) {
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
        <div style="font-size:32px">${ACH_ICONS[ach.icon] || '🏆'}</div>
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

  // ── Обновление счётчика задач (режим «Регламент») ────────────
  function _updateRegCounter() {
    const el = document.getElementById('reg-task-counter');
    if (!el) return;
    const done = _quests.filter(q => q.status === 'completed').length;
    el.textContent = `${done} / ${_quests.length} выполнено`;
  }

  // ── Рендер карточки активного квеста ─────────────────────────
  function _renderActiveCard() {
    if (_regulation) {
      _updateRegCounter();
      return;
    }
    const card    = document.getElementById('active-quest-card');
    const noQuest = document.getElementById('no-active-quest');
    if (!card || !noQuest) return;

    if (_activeQuest) {
      card.classList.remove('hidden');
      noQuest.classList.add('hidden');
      document.getElementById('quest-card-title').textContent = _activeQuest.title;
      document.getElementById('quest-card-desc').textContent  = _activeQuest.description;
      document.getElementById('quest-card-xp').textContent    = `+${_activeQuest.xp_reward} XP`;
      const label = document.getElementById('quest-card-label');
      if (label) label.textContent = `${ICONS[_activeQuest.type] || '🎯'} АКТИВНЫЙ КВЕСТ`;
    } else {
      card.classList.add('hidden');
      noQuest.classList.remove('hidden');
    }
  }

  // ── Переключение табов внутри модалки ────────────────────────
  function switchTab(tab) {
    _activeTab = tab;

    document.getElementById('qtab-quests')?.classList.toggle('active',       tab === 'quests');
    document.getElementById('qtab-achievements')?.classList.toggle('active', tab === 'achievements');
    document.getElementById('quest-list-panel')?.classList.toggle('hidden',       tab !== 'quests');
    document.getElementById('achievements-list-panel')?.classList.toggle('hidden', tab !== 'achievements');

    if (tab === 'achievements') _renderAchievements();
  }

  // ── Открытие / закрытие модалки ──────────────────────────────
  function openModal(tab = 'quests') {
    const modal = document.getElementById('quest-modal');
    if (!modal) return;
    modal.classList.add('open');
    switchTab(_regulation ? 'quests' : tab);
  }

  function closeModal() {
    document.getElementById('quest-modal')?.classList.remove('open');
  }

  return { load, start, complete, getActive, getAll, openModal, closeModal, switchTab, setRegulationMode };
})();
