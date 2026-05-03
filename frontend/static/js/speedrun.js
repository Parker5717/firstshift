/**
 * CASPER SpeedRun Tracker
 * Отслеживает прогресс квеста speed_run.
 * Показывает таскбар X/4, таймер обратного отсчёта.
 * Автоматически завершает квест когда все объекты найдены.
 */

const SpeedRun = (() => {
  let _active       = false;
  let _required     = [];      // маркеры которые нужно найти [0, 4, 1, 2]
  let _found        = new Set(); // найденные маркеры
  let _timeSec      = 180;
  let _startTime    = null;
  let _timerEl      = null;
  let _barEl        = null;
  let _container    = null;
  let _interval     = null;
  let _questSlug    = 'speed_explorer';

  // Иконки для маркеров
  const MARKER_ICONS = { 0: '🚪', 1: '🛑', 2: '⚙️', 4: '🧯' };
  const MARKER_NAMES = { 0: 'Вход', 1: 'Стоп', 2: 'Станок', 4: 'Огнет.' };

  function start(quest) {
    if (_active) return;
    const params = JSON.parse(quest.params_json || '{}');
    _required  = params.required_markers || [0, 4, 1, 2];
    _timeSec   = params.time_sec || 180;
    _found     = new Set();
    _startTime = Date.now();
    _questSlug = quest.slug;
    _active    = true;

    _createUI();
    _interval = setInterval(_tick, 500);
    console.log('[SpeedRun] Старт! Нужно найти:', _required);
  }

  function stop() {
    _active = false;
    clearInterval(_interval);
    _interval = null;
    _removeUI();
  }

  function onMarkerDetected(markerId) {
    if (!_active) return;
    if (!_required.includes(markerId)) return;
    if (_found.has(markerId)) return;

    _found.add(markerId);
    console.log('[SpeedRun] Найден маркер', markerId, `(${_found.size}/${_required.length})`);
    _updateUI();

    // Все найдены — завершаем квест
    if (_found.size >= _required.length) {
      _complete();
    }
  }

  async function _complete() {
    stop();
    console.log('[SpeedRun] Все объекты найдены! Завершаем квест.');
    const result = await QuestEngine.complete(_questSlug);
    if (result) {
      try { XPBar.update(await API.getProfile()); } catch (_) {}
    }
  }

  async function _fail() {
    stop();
    console.log('[SpeedRun] Время вышло!');
    // Показываем сообщение о провале
    const toast = document.createElement('div');
    toast.style.cssText = `
      position:fixed; top:50%; left:50%;
      transform:translate(-50%,-50%);
      background:rgba(7,11,20,0.97);
      border:1px solid var(--danger);
      border-radius:16px; padding:24px 32px;
      text-align:center; z-index:100;
      box-shadow:0 0 40px rgba(255,51,85,0.3);
    `;
    toast.innerHTML = `
      <div style="font-size:36px;margin-bottom:8px">⏰</div>
      <div style="font-size:18px;font-weight:700;color:var(--danger)">Время вышло!</div>
      <div style="font-size:13px;color:var(--text-secondary);margin-top:6px">
        Найдено: ${_found.size}/${_required.length} объектов
      </div>
      <div style="font-size:12px;color:var(--text-dim);margin-top:4px">Попробуй ещё раз!</div>
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);

    // Сбрасываем квест в available чтобы можно было попробовать снова
    try {
      await API.startQuest(_questSlug);
    } catch (_) {}
  }

  function _tick() {
    if (!_active) return;
    const elapsed = (Date.now() - _startTime) / 1000;
    const remaining = Math.max(0, _timeSec - elapsed);

    // Обновляем таймер
    if (_timerEl) {
      const m = Math.floor(remaining / 60);
      const s = Math.floor(remaining % 60);
      _timerEl.textContent = `${m}:${s.toString().padStart(2, '0')}`;
      _timerEl.style.color = remaining < 30 ? 'var(--danger)' : 'var(--success)';
    }

    if (remaining <= 0) {
      _fail();
    }
  }

  function _createUI() {
    _removeUI();
    _container = document.createElement('div');
    _container.id = 'speedrun-bar';
    _container.style.cssText = `
      position:fixed; top:60px; left:0; right:0;
      z-index:20; padding:8px 12px;
      background:rgba(7,11,20,0.92);
      border-bottom:1px solid var(--border-bright);
      backdrop-filter:blur(8px);
    `;

    _container.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
        <div style="font-size:11px;font-family:var(--font-mono);color:var(--warning);letter-spacing:1px">
          ⚡ БЫСТРЫЙ ОСМОТР
        </div>
        <div id="speedrun-timer" style="font-size:14px;font-weight:700;font-family:var(--font-mono);color:var(--success)">
          3:00
        </div>
      </div>
      <div id="speedrun-items" style="display:flex;gap:6px;margin-bottom:6px">
      </div>
      <div style="width:100%;height:4px;background:rgba(255,170,0,0.15);border-radius:4px;overflow:hidden">
        <div id="speedrun-progress" style="height:100%;background:linear-gradient(90deg,var(--warning),var(--success));border-radius:4px;width:0%;transition:width 0.3s ease;box-shadow:0 0 8px rgba(255,170,0,0.4)"></div>
      </div>
    `;

    document.body.appendChild(_container);
    _timerEl = document.getElementById('speedrun-timer');
    _barEl   = document.getElementById('speedrun-progress');
    _updateUI();
  }

  function _updateUI() {
    const itemsEl = document.getElementById('speedrun-items');
    if (itemsEl) {
      itemsEl.innerHTML = _required.map(mid => {
        const done = _found.has(mid);
        return `
          <div style="
            flex:1; padding:6px 4px; border-radius:8px; text-align:center;
            border:1px solid ${done ? 'var(--success)' : 'var(--border)'};
            background:${done ? 'rgba(0,255,136,0.1)' : 'var(--bg-glass)'};
            transition:all 0.3s;
          ">
            <div style="font-size:16px">${done ? '✅' : MARKER_ICONS[mid] || '❓'}</div>
            <div style="font-size:9px;color:${done ? 'var(--success)' : 'var(--text-dim)'};font-family:var(--font-mono)">${MARKER_NAMES[mid] || `ID${mid}`}</div>
          </div>
        `;
      }).join('');
    }

    if (_barEl) {
      _barEl.style.width = `${(_found.size / _required.length) * 100}%`;
    }
  }

  function _removeUI() {
    const el = document.getElementById('speedrun-bar');
    if (el) el.remove();
    _timerEl = null;
    _barEl   = null;
    _container = null;
  }

  function isActive() { return _active; }

  return { start, stop, onMarkerDetected, isActive };
})();
