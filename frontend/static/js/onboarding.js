/**
 * CASPER Onboarding
 * Показывает обучающий попап при первом входе нового пользователя.
 * Сохраняет флаг в sessionStorage — повторно не показывает.
 */

const Onboarding = (() => {
  const SEEN_KEY = 'casper_onboarding_done';

  const STEPS = [
    {
      icon: '🤖',
      title: 'Привет! Я КАСПЕР',
      text: 'Твой цифровой напарник на производстве. Я помогу освоиться, объясню правила и покажу где что находится.',
    },
    {
      icon: '🎯',
      title: 'Выполняй квесты',
      text: 'Нажми кнопку 🎯 справа чтобы открыть список квестов. Начни с «Первого шага» — он простой и даст тебе первый XP.',
    },
    {
      icon: '📷',
      title: 'Наводи камеру',
      text: 'Найди объект квеста, наведи камеру и держи секунду. Появится зелёная рамка и кнопка «Засчитать».',
    },
    {
      icon: '🏆',
      title: 'Получай уровни и ачивки',
      text: 'За квесты начисляется XP. Копи опыт — расти от Стажёра до Специалиста. Ачивки открывают бонусный XP.',
    },
    {
      icon: '🖨️',
      title: 'Маркеры для объектов',
      text: 'Распечатай маркеры на странице /markers и прикрепи к объектам в цеху — тогда камера их распознает.',
    },
  ];

  let _current = 0;
  let _overlay = null;

  function maybeShow() {
    if (sessionStorage.getItem(SEEN_KEY)) return;
    _current = 0;
    _show();
  }

  function _show() {
    if (_overlay) _overlay.remove();

    _overlay = document.createElement('div');
    _overlay.style.cssText = `
      position:fixed; inset:0; z-index:100;
      background:rgba(7,11,20,0.88);
      backdrop-filter:blur(6px);
      display:flex; align-items:center; justify-content:center;
      padding:24px;
      animation: fadeIn 0.3s ease;
    `;

    const step = STEPS[_current];
    const isLast = _current === STEPS.length - 1;

    _overlay.innerHTML = `
      <style>
        @keyframes fadeIn { from{opacity:0;transform:scale(0.95)} to{opacity:1;transform:scale(1)} }
      </style>
      <div style="
        width:100%; max-width:360px;
        background:var(--bg-dark);
        border:1px solid var(--border-bright);
        border-radius:20px;
        padding:28px 24px 24px;
        text-align:center;
        box-shadow:0 0 60px rgba(0,170,255,0.2);
      ">
        <div style="font-size:56px;margin-bottom:16px">${step.icon}</div>
        <div style="font-size:20px;font-weight:800;color:var(--text-primary);margin-bottom:10px">${step.title}</div>
        <div style="font-size:14px;color:var(--text-secondary);line-height:1.65;margin-bottom:24px">${step.text}</div>

        <!-- Индикатор прогресса -->
        <div style="display:flex;justify-content:center;gap:6px;margin-bottom:24px">
          ${STEPS.map((_, i) => `
            <div style="
              width:${i === _current ? 20 : 8}px; height:8px;
              border-radius:4px;
              background:${i === _current ? 'var(--accent)' : 'var(--border)'};
              transition:all 0.3s;
            "></div>
          `).join('')}
        </div>

        <div style="display:flex;gap:10px">
          <button id="ob-skip" style="
            flex:1; padding:12px;
            background:transparent; border:1px solid var(--border);
            border-radius:10px; color:var(--text-secondary);
            font-size:13px; cursor:pointer;
          ">Пропустить</button>
          <button id="ob-next" style="
            flex:2; padding:12px;
            background:var(--accent); border:none;
            border-radius:10px; color:var(--bg-dark);
            font-size:15px; font-weight:700; cursor:pointer;
          ">${isLast ? '🚀 Начать!' : 'Далее →'}</button>
        </div>
      </div>
    `;

    document.body.appendChild(_overlay);

    document.getElementById('ob-skip').addEventListener('click', _done);
    document.getElementById('ob-next').addEventListener('click', () => {
      if (isLast) _done();
      else { _current++; _show(); }
    });
  }

  function _done() {
    sessionStorage.setItem(SEEN_KEY, '1');
    if (_overlay) {
      _overlay.style.opacity = '0';
      _overlay.style.transition = 'opacity 0.3s';
      setTimeout(() => { _overlay?.remove(); _overlay = null; }, 300);
    }
    // После онбординга маскот говорит приветствие
    if (typeof Mascot !== 'undefined') {
      setTimeout(() => Mascot.say('welcome'), 500);
    }
  }

  return { maybeShow };
})();
