/**
 * CASPER Quest Engine
 * Управляет состоянием квестов на фронтенде.
 */

const QuestEngine = (() => {
  let _quests = [];
  let _activeQuest = null;

  const ICONS = {
    discovery:  '🔍',
    safety:     '🦺',
    knowledge:  '📚',
    speed_run:  '⚡',
  };

  const STATUS_LABELS = {
    available:  'Доступен',
    active:     'Активен',
    completed:  'Выполнен',
    locked:     'Заблокирован',
    failed:     'Провален',
  };

  /**
   * Загрузить квесты с сервера и обновить UI.
   */
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

  /**
   * Начать квест.
   */
  async function start(slug) {
    try {
      await API.startQuest(slug);
      if (typeof Mascot !== 'undefined') Mascot.onQuestStart();
      await load();
      // Запускаем SpeedRun трекер если это speed_run квест
      const quest = _quests.find(q => q.slug === slug);
      if (quest && quest.type === 'speed_run' && typeof SpeedRun !== 'undefined') {
        SpeedRun.start(quest);
      }
      return true;
    } catch (err) {
      if (typeof Mascot !== 'undefined') Mascot.onError();
      alert(`Не удалось начать квест: ${err.message}`);
      return false;
    }
  }

  /**
   * Завершить активный квест (вызывается после успешного сканирования).
   */
  async function complete(slug) {
    try {
      const result = await API.completeQuest(slug);
      if (typeof SpeedRun !== 'undefined') SpeedRun.stop();
      XPBar.showXPGain(result.xp_gained, result.leveled_up, result.new_level, result.message);
      AROverlay.flashSuccess();
      if (typeof Mascot !== 'undefined') {
        if (result.leveled_up) Mascot.onLevelUp();
        else Mascot.onQuestComplete();
      }
      if (result.newly_unlocked_achievements?.length > 0) {
        setTimeout(() => Achievements.notifyNew(result.newly_unlocked_achievements), 1500);
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

  // ---- Рендер списка квестов в модалке ----
  function _renderQuestList() {
    const list = document.getElementById('quest-list');
    if (!list) return;

    list.innerHTML = '';
    _quests.forEach(q => {
      const item = document.createElement('div');
      item.className = `quest-item ${q.status}`;
      item.innerHTML = `
        <div class="quest-item-icon">${ICONS[q.type] || '🎯'}</div>
        <div class="quest-item-info">
          <div class="quest-item-title">${q.title}</div>
          <div class="quest-item-xp">+${q.xp_reward} XP</div>
        </div>
        <span class="badge badge-${q.status}">${STATUS_LABELS[q.status] || q.status}</span>
      `;

      if (q.status === 'available') {
        item.addEventListener('click', async () => {
          if (confirm(`Начать квест «${q.title}»?\n\n${q.description}`)) {
            await start(q.slug);
            closeModal();
          }
        });
      } else if (q.status === 'active') {
        item.addEventListener('click', () => {
          closeModal();
          _renderActiveCard();
        });
      }

      list.appendChild(item);
    });
  }

  // ---- Рендер карточки активного квеста в нижней панели ----
  function _renderActiveCard() {
    const card = document.getElementById('active-quest-card');
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

  function openModal() {
    const modal = document.getElementById('quest-modal');
    const inner = document.getElementById('quest-modal-inner');
    if (!modal) return;
    modal.style.opacity = '1';
    modal.style.pointerEvents = 'all';
    if (inner) inner.style.transform = 'translateY(0)';
  }

  function closeModal() {
    const modal = document.getElementById('quest-modal');
    const inner = document.getElementById('quest-modal-inner');
    if (!modal) return;
    modal.style.opacity = '0';
    modal.style.pointerEvents = 'none';
    if (inner) inner.style.transform = 'translateY(100%)';
  }

  return { load, start, complete, getActive, getAll, openModal, closeModal };
})();
