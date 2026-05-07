/**
 * FirstShift Mascot v3 — локальные MP3 + Web Speech fallback.
 *
 * Режимы:
 *   'text'  — только текст (по умолчанию)
 *   'voice' — текст + аудио из /static/sounds/mascot/*.mp3
 *
 * MP3 файлы генерируются скриптом generate_voice.py (gTTS, Google качество).
 * Если MP3 нет — fallback на Web Speech API.
 */

const Mascot = (() => {
  // Привязка контекста → MP3 файлы (несколько вариантов — рандомно)
  const AUDIO_MAP = {
    welcome:        ['welcome_0', 'welcome_1', 'welcome_2'],
    quest_start:    ['quest_start_0', 'quest_start_1', 'quest_start_2'],
    quest_complete: ['quest_complete_0', 'quest_complete_1', 'quest_complete_2'],
    levelup:        ['levelup_0', 'levelup_1', 'levelup_2'],
    idle:           ['idle_0', 'idle_1', 'idle_2'],
    stress_relief:  ['stress_0', 'stress_1', 'stress_2', 'stress_3'],
    error:          ['error_0', 'error_1'],
    safety_ok:      ['safety_ok_0', 'safety_ok_1'],
  };

  // Текст фраз (для пузыря и Web Speech fallback)
  const PHRASES = {
    welcome: [
      "Привет! Я Алекс — твой напарник на производстве. Поехали разбираться!",
      "Добро пожаловать! Первый день — это просто первый шаг. Буду рядом.",
      "Алекс на связи. Несколько квестов — и цех станет тебе как свой. Начнём?",
    ],
    quest_start: [
      "Отличный выбор! Наведи камеру на объект и держи пару секунд — засчитается.",
      "Поехали! Подсказки всегда внизу экрана.",
      "Главное — внимательность. Не торопись, всё получится.",
    ],
    quest_complete: [
      "Готово! Вот так и копится настоящий опыт — шаг за шагом.",
      "Выполнено! Ещё несколько таких — и цех станет как родной.",
      "Отлично! Я знал, что получится. Следующий?",
    ],
    levelup: [
      "Уровень вырос! Растёшь на глазах — так держать!",
      "Новый уровень! Знания о производстве прибавились. Чувствуется?",
      "Прокачка принята! Продолжай — скоро сам будешь учить других.",
    ],
    idle: [
      "Видишь прицел внизу? Там квесты — попробуй следующий!",
      "Наведи камеру на объект в цехе. Вдруг найдём что-то интересное.",
      "Есть свободная минута? В заданиях ещё много нового.",
    ],
    stress_relief: [
      "Ошибиться — нормально. Здесь учатся, а не наказывают.",
      "Непонятно? Спроси наставника — нет вопросов, которых стоит стесняться.",
      "Первый день всегда самый трудный. Завтра будет легче — обещаю.",
      "Ты справляешься. Каждый опытный сотрудник начинал точно так же.",
    ],
    error: [
      "Не получилось — попробуй ещё раз. Подержи немного дольше.",
      "Бывает! Камере иногда нужна пара секунд. Поднеси поближе.",
    ],
    safety_ok: [
      "Снаряжение в порядке! Хорошая смена начинается с безопасности.",
      "Каска и жилет на месте. Всё правильно — вперёд!",
    ],
  };

  const SOUNDS_PATH = '/static/sounds/mascot/';
  const MODE_KEY    = 'firstshift_mascot_mode';

  let _mode      = sessionStorage.getItem(MODE_KEY) || 'text';
  let _container = null;
  let _bubble    = null;
  let _avatar    = null;
  let _modeBtn   = null;
  let _idleTimer = null;
  let _queue     = [];
  let _isShowing = false;
  let _audio     = null;   // текущий Audio объект

  function init() {
    _createDOM();
    setTimeout(() => say('welcome'), 2000);
    _resetIdleTimer();
  }

  function _createDOM() {
    _container = document.createElement('div');
    _container.id = 'mascot-wrap';
    _container.style.cssText = `
      position:fixed; bottom:160px; left:12px; z-index:40;
      display:flex; flex-direction:column; align-items:flex-start; gap:8px;
    `;

    _bubble = document.createElement('div');
    _bubble.style.cssText = `
      display:none; max-width:220px;
      padding:11px 14px;
      background:rgba(7,11,20,0.96);
      border:1px solid var(--accent);
      border-radius:12px 12px 12px 4px;
      color:var(--text-primary);
      font-size:13px; line-height:1.55;
      box-shadow:0 0 20px rgba(212,118,78,0.25);
      cursor:pointer;
    `;
    _bubble.addEventListener('click', _stopAndHide);

    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;gap:8px';

    _avatar = document.createElement('div');
    _avatar.style.cssText = `
      width:60px; height:60px; border-radius:50%;
      border:2px solid var(--accent);
      overflow:hidden;
      box-shadow:0 0 16px rgba(212,118,78,0.45);
      cursor:pointer; flex-shrink:0;
      transition:transform 0.2s;
      background:transparent;
    `;
    _avatar.innerHTML = '<img src="/static/img/mascot.svg" alt="Алекс" style="width:100%;height:100%;display:block">';
    _avatar.title = 'Алекс — нажми для подсказки';
    _avatar.addEventListener('click', () => {
      if (_isShowing) _stopAndHide();
      else say('idle');
    });
    _avatar.addEventListener('mouseenter', () => { _avatar.style.transform = 'scale(1.1)'; });
    _avatar.addEventListener('mouseleave', () => { _avatar.style.transform = 'scale(1)'; });

    _modeBtn = document.createElement('button');
    _modeBtn.style.cssText = `
      width:32px; height:32px; border-radius:50%;
      background:var(--bg-panel); border:1px solid var(--border);
      color:var(--text-secondary); font-size:15px; cursor:pointer;
      display:flex; align-items:center; justify-content:center;
      transition:all 0.2s; flex-shrink:0;
    `;
    _modeBtn.addEventListener('click', _toggleMode);
    _updateModeBtn();

    row.appendChild(_bubble);
    row.appendChild(_avatar);
    _container.appendChild(row);
    _container.appendChild(_modeBtn);
    document.body.appendChild(_container);
  }

  function _toggleMode() {
    _mode = _mode === 'text' ? 'voice' : 'text';
    sessionStorage.setItem(MODE_KEY, _mode);
    _updateModeBtn();
    if (_mode === 'voice') {
      _showBubble('Озвучка включена! Говорю голосом 🔊', true);
      setTimeout(() => _playAudio('welcome_0'), 500);
    } else {
      _stopAudio();
      _showBubble('Только текст. Нажми 🔇 для озвучки.', true);
    }
  }

  function _updateModeBtn() {
    if (!_modeBtn) return;
    const on = _mode === 'voice';
    _modeBtn.textContent   = on ? '🔊' : '🔇';
    _modeBtn.style.borderColor = on ? 'var(--accent)' : 'var(--border)';
    _modeBtn.style.color   = on ? 'var(--accent)' : 'var(--text-secondary)';
    _modeBtn.title = on ? 'Выключить озвучку' : 'Включить озвучку';
  }

  function _playAudio(fileKey) {
    _stopAudio();
    const url = `${SOUNDS_PATH}${fileKey}.mp3`;
    _audio = new Audio(url);
    _audio.volume = 0.95;
    _audio.onerror = () => console.warn('[Mascot] MP3 не найден:', fileKey);
    _audio.play().catch(() => {});
  }

  function _stopAudio() {
    if (_audio) {
      _audio.pause();
      _audio.src = '';
      _audio = null;
    }
  }

  // ---- Основная логика ----

  function say(context, customText = null) {
    _resetIdleTimer();
    const phrases = PHRASES[context] || PHRASES.idle;
    const idx = Math.floor(Math.random() * phrases.length);
    const text = customText || phrases[idx];
    const audioKeys = AUDIO_MAP[context] || [];
    const audioKey  = audioKeys[idx % audioKeys.length] || null;
    _queue.push({ text, audioKey });
    if (!_isShowing) _showNext();
  }

  function _showNext() {
    if (_queue.length === 0) { _isShowing = false; return; }
    _isShowing = true;
    const { text, audioKey } = _queue.shift();
    _showBubble(text);
    if (_mode === 'voice' && audioKey) _playAudio(audioKey);
  }

  function _showBubble(text, immediate = false) {
    _bubble.textContent = text;
    _bubble.style.display = 'block';
    _bubble.style.opacity = '0';
    setTimeout(() => { _bubble.style.opacity = '1'; _bubble.style.transition = 'opacity 0.3s'; }, 10);

    const delay = _mode === 'voice' ? 6000 : 5000;
    setTimeout(() => {
      _hideBubble();
      if (!immediate) setTimeout(_showNext, 400);
    }, delay);
  }

  function _hideBubble() {
    _bubble.style.opacity = '0';
    setTimeout(() => { _bubble.style.display = 'none'; _isShowing = false; }, 300);
  }

  function _stopAndHide() {
    _queue = [];
    _stopAudio();
    _hideBubble();
  }

  function _resetIdleTimer() {
    clearTimeout(_idleTimer);
    _idleTimer = setTimeout(() => {
      say(Math.random() > 0.5 ? 'idle' : 'stress_relief');
    }, 90000);
  }

  function onQuestStart()    { say('quest_start'); _resetIdleTimer(); }
  function onQuestComplete() { say('quest_complete'); _resetIdleTimer(); }
  function onLevelUp()       { say('levelup'); _resetIdleTimer(); }
  function onError()         { say('error'); }
  function onSafetyOk()      { say('safety_ok'); }

  function disable() {
    clearTimeout(_idleTimer);
    _queue = [];
    if (_container) _container.style.display = 'none';
  }

  return { init, say, onQuestStart, onQuestComplete, onLevelUp, onError, onSafetyOk, disable };
})();
