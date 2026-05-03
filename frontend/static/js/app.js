/**
 * CASPER AR Assistant — главный модуль app.html
 * Связывает: Camera, AROverlay, XPBar, QuestEngine, API.
 */

(async () => {
  // Проверка авторизации
  if (!API.hasToken()) {
    window.location.href = '/';
    return;
  }

  // DOM-элементы
  const videoEl     = document.getElementById('video');
  const canvasEl    = document.getElementById('ar-canvas');
  const btnToggle   = document.getElementById('btn-toggle-camera');
  const btnQuests   = document.getElementById('btn-quests');
  const btnLogout   = document.getElementById('btn-logout');
  const cameraError = document.getElementById('camera-error');
  const btnRetry    = document.getElementById('btn-retry-camera');

  // ---- Инициализация AR-оверлея ----
  AROverlay.init(canvasEl);

  // ---- Инициализация vision-клиента ----
  VisionClient.init();

  // ---- Инициализация маскота ----
  Mascot.init();

  // ---- Запуск камеры ----
  async function startCamera(facingMode = 'environment') {
    const ok = await Camera.start(videoEl, facingMode);
    if (!ok) {
      cameraError.classList.remove('hidden');
      videoEl.classList.add('hidden');
      VisionClient.stop();
    } else {
      cameraError.classList.add('hidden');
      videoEl.classList.remove('hidden');
      const isPPE = facingMode === 'user';
      VisionClient.start(videoEl, isPPE);
    }
  }

  if (!Camera.isSupported()) {
    cameraError.classList.remove('hidden');
    videoEl.classList.add('hidden');
  } else {
    await startCamera('environment');
  }

  // ---- Загрузка профиля ----
  try {
    const profile = await API.getProfile();
    XPBar.update(profile);
    // Сбрасываем флаг онбординга для новых пользователей
    // (< 50 XP = ни одного квеста не завершено, safety check даёт 25 XP через ачивку)
    if (profile.total_xp < 50) {
      sessionStorage.removeItem('casper_onboarding_done');
    }
    // Онбординг показываем только после проверки XP
    setTimeout(() => Onboarding.maybeShow(), 300);
  } catch (err) {
    console.error('Ошибка загрузки профиля:', err);
    // Если профиль не загрузился — всё равно показываем онбординг
    setTimeout(() => Onboarding.maybeShow(), 300);
  }

  // ---- Загрузка квестов ----
  await QuestEngine.load();

  // Если speed_run квест уже активен (например после перезагрузки) — запускаем трекер
  const activeQuest = QuestEngine.getActive();
  if (activeQuest && activeQuest.type === 'speed_run') {
    SpeedRun.start(activeQuest);
  }

  // ---- Обработчики кнопок ----

  // Переключение камеры
  btnToggle.addEventListener('click', async () => {
    btnToggle.textContent = '⏳';
    const mode = await Camera.toggle();
    btnToggle.textContent = mode === 'environment' ? '🔄' : '🤳';
  });

  // Открыть список квестов
  btnQuests.addEventListener('click', () => QuestEngine.openModal());

  // Ачивки
  const btnAchievements = document.getElementById('btn-achievements');
  if (btnAchievements) {
    btnAchievements.addEventListener('click', () => Achievements.openModal());
  }
  const btnCloseAch = document.getElementById('btn-close-achievements');
  if (btnCloseAch) {
    btnCloseAch.addEventListener('click', () => Achievements.closeModal());
  }
  const achModal = document.getElementById('achievements-modal');
  if (achModal) {
    achModal.addEventListener('click', e => {
      if (e.target === achModal) Achievements.closeModal();
    });
  }

  // Закрыть модалку кликом на фон
  document.getElementById('quest-modal').addEventListener('click', e => {
    if (e.target === document.getElementById('quest-modal')) QuestEngine.closeModal();
  });
  document.getElementById('btn-close-modal').addEventListener('click', () => QuestEngine.closeModal());

  // Выход
  if (btnLogout) {
    btnLogout.addEventListener('click', () => {
      if (confirm('Выйти из аккаунта?')) {
        Camera.stop();
        AROverlay.stop();
        API.clearToken();
        window.location.href = '/';
      }
    });
  }

  // Повтор подключения камеры
  if (btnRetry) {
    btnRetry.addEventListener('click', () => startCamera(Camera.getFacingMode()));
  }

  // Клик по карточке активного квеста
  document.getElementById('active-quest-card').addEventListener('click', () => {
    QuestEngine.openModal();
  });

  // ---- Обновление профиля раз в 30 секунд ----
  setInterval(async () => {
    try {
      const profile = await API.getProfile();
      XPBar.update(profile);
    } catch (_) {}
  }, 30_000);

  console.log('[CASPER] AR Assistant ready 🚀');


})();
