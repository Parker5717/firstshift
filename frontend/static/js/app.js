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
    if (['hr', 'admin'].includes(profile.role)) {
      const adminTab = document.getElementById('tab-admin');
      if (adminTab) adminTab.style.display = 'flex';
    }
    if (profile.total_xp < 50) sessionStorage.removeItem('casper_onboarding_done');
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
