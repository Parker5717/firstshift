/**
 * CASPER Mascot v3 — локальные MP3 + Web Speech fallback.
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
      "Привет! Я КАСПЕР — твой цифровой напарник. Вместе разберёмся с цехом! 🤖",
      "Добро пожаловать на производство! Не переживай, я буду рядом. 🚀",
      "Первый день? Отлично! Начнём с простого — я покажу как тут всё устроено.",
    ],
    quest_start: [
      "Отличный выбор! Наведи камеру и держи пару секунд. Ты справишься!",
      "Поехали! Если что-то непонятно — просто наведи камеру на объект.",
      "Этот квест несложный. Главное — не торопись и смотри внимательно.",
    ],
    quest_complete: [
      "Отлично! Вот это я понимаю — профессионал растёт! 🌟",
      "Так держать! Каждый выполненный квест — шаг к уверенной работе.",
      "Молодец! Ты уже знаешь больше, чем 10 минут назад. 💪",
    ],
    levelup: [
      "Уровень получен! Ты растёшь прямо на глазах! 🎉",
      "Новый уровень — новые возможности! Продолжай в том же духе!",
      "Вот это прокачка! Скоро будешь учить других. 🏆",
    ],
    idle: [
      "Псс... видишь кнопку 🎯? Там квесты. Попробуй один!",
      "Скучно стоять? Наведи камеру куда-нибудь — вдруг что найдём!",
      "Знаешь что? Начни с первого квеста — это быстро и весело.",
    ],
    stress_relief: [
      "Не бойся ошибиться — это часть обучения. Я не буду ругаться! 🤗",
      "Здесь нет неправильных вопросов. Спрашивай у наставника всё что непонятно.",
      "Первый день всегда кажется сложным. Завтра будет легче, обещаю!",
      "Ты справляешься отлично! Каждый начинал с нуля.",
    ],
    error: [
      "Упс! Бывает. Попробуй ещё раз — никто не ошибается только тот, кто ничего не делает. 😊",
      "Не вышло? Не проблема! Я верю что у тебя получится.",
    ],
    safety_ok: [
      "Снаряжение в порядке! Безопасная смена — это хорошая смена.",
      "Отлично! Все СИЗ на месте. Можно начинать работу.",
    ],
  };

  const SOUNDS_PATH = '/static/sounds/mascot/';
  const MODE_KEY    = 'casper_mascot_mode';

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
      box-shadow:0 0 20px rgba(0,170,255,0.2);
      cursor:pointer;
    `;
    _bubble.addEventListener('click', _stopAndHide);

    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;gap:8px';

    _avatar = document.createElement('div');
    _avatar.style.cssText = `
      width:50px; height:50px; border-radius:50%;
      background:linear-gradient(135deg,#0055aa,#00aaff);
      border:2px solid var(--accent);
      display:flex; align-items:center; justify-content:center;
      font-size:24px;
      box-shadow:0 0 14px rgba(0,170,255,0.35);
      cursor:pointer; flex-shrink:0;
      transition:transform 0.2s;
    `;
    _avatar.textContent = '🤖';
    _avatar.title = 'КАСПЕР — нажми для подсказки';
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

  return { init, say, onQuestStart, onQuestComplete, onLevelUp, onError, onSafetyOk };
})();
