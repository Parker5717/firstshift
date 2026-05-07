/**
 * FirstShift AR — главный модуль app.html
 * Связывает: Camera, AROverlay, XPBar, QuestEngine, VisionClient, Mascot.
 */

(async () => {
  if (!API.hasToken()) {
    window.location.href = '/';
    return;
  }

  const videoEl     = document.getElementById('video');
  const canvasEl    = document.getElementById('ar-canvas');
  const cameraError = document.getElementById('camera-error');
  const btnRetry    = document.getElementById('btn-retry-camera');

  // ── Инициализация ──────────────────────────────────────────
  AROverlay.init(canvasEl);
  VisionClient.init();
  Mascot.init();

  // ── Камера ─────────────────────────────────────────────────
  async function startCamera(facingMode = 'environment') {
    const ok = await Camera.start(videoEl, facingMode);
    if (!ok) {
      cameraError.classList.remove('hidden');
      videoEl.classList.add('hidden');
      VisionClient.stop();
    } else {
      cameraError.classList.add('hidden');
      videoEl.classList.remove('hidden');
      VisionClient.start(videoEl, facingMode === 'user');
    }
  }

  if (!Camera.isSupported()) {
    cameraError.classList.remove('hidden');
    videoEl.classList.add('hidden');
  } else {
    await startCamera('environment');
  }

  // ── Профиль ────────────────────────────────────────────────
  try {
    const profile = await API.getProfile();
    XPBar.update(profile);
    // Показываем Admin кнопку для hr и admin
    // Кнопка Наставник для роли mentor
    if (profile.role === 'mentor') {
      const mentorTab = document.getElementById('tab-mentor');
      if (mentorTab) mentorTab.style.display = 'flex';
    }
    if (['hr', 'admin'].includes(profile.role)) {
      const adminTab = document.getElementById('tab-admin');
      if (adminTab) adminTab.style.display = 'flex';
    }
    // Кнопка очистки кэша — только для admin (для отладки в Opera GX и др.)
    if (profile.role === 'admin') {
      const cacheBtn = document.getElementById('btn-clear-cache');
      if (cacheBtn) cacheBtn.style.display = 'block';
    }
    // Regulation mode для сотрудников 30+ лет — без геймификации
    if (profile.ui_mode === 'regulation') {
      QuestEngine.setRegulationMode();

      // Убрать XP-бар и уровень, оставить имя + счётчик задач
      const levelLabel = document.getElementById('hud-level-label');
      if (levelLabel) levelLabel.style.display = 'none';
      const xpBar = document.getElementById('hud-xp-bar');
      if (xpBar) xpBar.style.display = 'none';
      const headerRow = document.getElementById('hud-header-row');
      if (headerRow) {
        const ctr = document.createElement('span');
        ctr.id = 'reg-task-counter';
        ctr.style.cssText = 'font-size:12px;font-family:var(--font-mono);color:var(--accent);white-space:nowrap;margin-left:8px';
        headerRow.appendChild(ctr);
      }

      // Скрыть карточку активного квеста внизу
      const hudBottom = document.getElementById('hud-bottom');
      if (hudBottom) hudBottom.style.display = 'none';

      // Скрыть всплывающие окна XP и level-up
      const xpPopup = document.getElementById('xp-popup');
      if (xpPopup) xpPopup.style.display = 'none';
      const levelupPopup = document.getElementById('levelup-popup');
      if (levelupPopup) levelupPopup.style.display = 'none';

      // Отключить маскота
      if (typeof Mascot !== 'undefined') Mascot.disable();

      // Переименовать вкладку «Задания» → «Задачи»
      const tabLabel = document.querySelector('#tab-quests .tab-label');
      if (tabLabel) tabLabel.textContent = 'Задачи';

      // Открыть список задач
      setTimeout(() => QuestEngine.openModal('quests'), 600);
    }

    // Скрыть квесты и XP для не-сотрудников
    if (profile.role !== 'employee') {
      const hudBottom = document.getElementById('hud-bottom');
      if (hudBottom) hudBottom.style.display = 'none';
      const tabQuests = document.getElementById('tab-quests');
      if (tabQuests) tabQuests.style.display = 'none';
      const hudXpBar = document.getElementById('hud-xp-bar');
      if (hudXpBar) hudXpBar.style.display = 'none';
      const hudLevel = document.getElementById('hud-level-label');
      if (hudLevel) hudLevel.style.display = 'none';
    }
    if (profile.total_xp < 50) localStorage.removeItem('firstshift_onboarding_done');
    setTimeout(() => Onboarding.maybeShow(), 300);
  } catch (err) {
    console.error('[App] Ошибка загрузки профиля:', err);
    setTimeout(() => Onboarding.maybeShow(), 300);
  }

  // ── Квесты ─────────────────────────────────────────────────
  await QuestEngine.load();

  const activeQuest = QuestEngine.getActive();
  if (activeQuest?.type === 'speed_run' && typeof SpeedRun !== 'undefined') {
    SpeedRun.start(activeQuest);
  }

  // ── Обработчики ────────────────────────────────────────────

  // Повтор камеры
  btnRetry?.addEventListener('click', () => startCamera(Camera.getFacingMode()));

  // Карточка активного квеста → открыть модалку
  document.getElementById('active-quest-card')?.addEventListener('click', () => {
    QuestEngine.openModal('quests');
  });

  // Клик по фону модалки → закрыть
  document.getElementById('quest-modal')?.addEventListener('click', e => {
    if (e.target === document.getElementById('quest-modal')) QuestEngine.closeModal();
  });

  // Кнопка камеры в tab bar переключает через Camera.toggle()
  // (обработчик уже в inline-скрипте app.html через Tab.camera())

  // ── Обновление профиля раз в 30 сек ───────────────────────
  setInterval(async () => {
    try { XPBar.update(await API.getProfile()); } catch (_) {}
  }, 30_000);

  console.log('[FirstShift] AR ready 🚀');
})();
