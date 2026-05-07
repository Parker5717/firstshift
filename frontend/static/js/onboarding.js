/**
 * FirstShift Onboarding
 * Показывает обучающий попап при первом входе.
 * Контент зависит от роли пользователя.
 */

const Onboarding = (() => {
  const SEEN_KEY = 'firstshift_onboarding_done';

  // ── Шаги по ролям ────────────────────────────────────────────────────────

  const STEPS_EMPLOYEE = [
    {
      icon: '<img src="/static/img/mascot.png" alt="Алекс" style="width:56px;height:56px;display:inline-block">',
      title: 'Привет! Я Алекс',
      text: 'Твой цифровой напарник на производстве. Помогу освоиться, покажу где что находится и объясню правила безопасности.',
    },
    {
      icon: '🛡️',
      title: 'Safety Check при входе',
      text: 'Каждый день при входе в смену проходи проверку снаряжения — каска и жилет. Это занимает 10 секунд.',
    },
    {
      icon: '🎯',
      title: 'Выполняй квесты',
      text: 'Нажми «Задания» внизу чтобы открыть список. Начни с «Первого шага» — наведи камеру на маркер у входа.',
    },
    {
      icon: '📷',
      title: 'Как работает камера',
      text: 'Найди объект квеста, наведи заднюю камеру и держи 3 секунды. Система сама засчитает квест когда распознает маркер.',
    },
    {
      icon: '🏆',
      title: 'XP и достижения',
      text: 'За квесты получаешь опыт и растёшь от Стажёра до Специалиста. Открывай достижения и попадай в лидерборд!',
    },
  ];

  const STEPS_MENTOR = [
    {
      icon: '<img src="/static/img/mascot.png" alt="Алекс" style="width:56px;height:56px;display:inline-block">',
      title: 'Привет! Я Алекс',
      text: 'Панель наставника FirstShift. Ты отвечаешь за адаптацию новых сотрудников на производстве.',
    },
    {
      icon: '👥',
      title: 'Твои подопечные',
      text: 'HR назначит тебе новых сотрудников. Следи за их прогрессом в разделе «Профиль» → перейди в панель наставника.',
    },
    {
      icon: '📊',
      title: 'Прогресс онбординга',
      text: 'Ты видишь кто прошёл Safety Check, какие квесты выполнены и на каком уровне твои подопечные.',
    },
    {
      icon: '🔔',
      title: 'Уведомления',
      text: 'Ты будешь получать уведомления когда подопечный повышает уровень или пропускает Safety Check.',
    },
  ];

  const STEPS_HR = [
    {
      icon: '<img src="/static/img/mascot.png" alt="Алекс" style="width:56px;height:56px;display:inline-block">',
      title: 'Добро пожаловать в FirstShift',
      text: 'Панель HR-менеджера. Здесь ты управляешь адаптацией всех сотрудников предприятия.',
    },
    {
      icon: '⚙️',
      title: 'Панель администратора',
      text: 'Нажми кнопку «Admin» в правом нижнем углу. Там список всех сотрудников, их прогресс и статус Safety Check.',
    },
    {
      icon: '👤',
      title: 'Назначай наставников',
      text: 'В панели Admin → строка сотрудника → колонка «Наставник». Выбери наставника из списка.',
    },
    {
      icon: '📄',
      title: 'PDF-отчёты',
      text: 'Кликни на сотрудника в панели Admin → внизу боковой панели кнопки «PDF за 7 дней» и «PDF за 30 дней».',
    },
    {
      icon: '🛡️',
      title: 'Safety Check журнал',
      text: 'В панели Admin → раздел Safety Check. Видишь кто прошёл проверку сегодня, а кто нет.',
    },
  ];

  const STEPS_ADMIN = [
    {
      icon: '<img src="/static/img/mascot.png" alt="Алекс" style="width:56px;height:56px;display:inline-block">',
      title: 'Добро пожаловать, администратор',
      text: 'У тебя полный доступ к платформе FirstShift. Управляй ролями, наставниками и данными всех пользователей.',
    },
    {
      icon: '⚙️',
      title: 'Панель Admin',
      text: 'Кнопка «Admin» внизу → полный список сотрудников, смена ролей, назначение наставников, PDF-отчёты.',
    },
    {
      icon: '🔑',
      title: 'Управление ролями',
      text: 'В панели Admin → колонка «Управление» → дропдаун роли. Назначь HR-менеджерам роль hr, наставникам — mentor.',
    },
    {
      icon: '🧹',
      title: 'Очистка кэша',
      text: 'Если интерфейс не обновляется — открой localhost:8000/clear и нажми кнопку. Это сбросит кэш браузера.',
    },
  ];

  const STEPS_REGULATION = [
    {
      icon: '👷',
      title: 'Добро пожаловать в FirstShift',
      text: 'Здесь собраны все задачи вашего онбординга. Выполняйте их по порядку — это займёт несколько смен.',
    },
    {
      icon: '🛡️',
      title: 'Safety Check при входе',
      text: 'Каждый день при входе в смену проходите проверку снаряжения — каска и жилет обязательны. Это занимает 10 секунд.',
    },
    {
      icon: '📋',
      title: 'Список задач',
      text: 'Нажмите «Задачи» внизу экрана чтобы открыть список. Начните с первой доступной задачи и выполняйте по порядку.',
    },
    {
      icon: '📷',
      title: 'Как работает камера',
      text: 'Найдите объект задачи, наведите заднюю камеру и держите 3 секунды. Система засчитает задачу автоматически.',
    },
  ];

  const STEPS_BY_ROLE = {
    employee: STEPS_EMPLOYEE,
    mentor:   STEPS_MENTOR,
    hr:       STEPS_HR,
    admin:    STEPS_ADMIN,
  };

  let _current    = 0;
  let _steps      = STEPS_EMPLOYEE;
  let _overlay    = null;
  let _regulation = false;

  // ── Публичный API ─────────────────────────────────────────────────────────

  async function maybeShow() {
    if (localStorage.getItem(SEEN_KEY)) return;

    // Определяем роль и выбираем шаги
    try {
      const profile = await API.getProfile();
      _regulation = profile.ui_mode === 'regulation';
      _steps = _regulation
        ? STEPS_REGULATION
        : (STEPS_BY_ROLE[profile.role] || STEPS_EMPLOYEE);
    } catch (_) {
      _steps = STEPS_EMPLOYEE;
    }

    _current = 0;
    _show();
  }

  // ── Рендер ────────────────────────────────────────────────────────────────

  function _show() {
    if (_overlay) _overlay.remove();

    const step   = _steps[_current];
    const isLast = _current === _steps.length - 1;

    _overlay = document.createElement('div');
    _overlay.style.cssText = `
      position:fixed; inset:0; z-index:100;
      background:rgba(13,11,9,0.92);
      backdrop-filter:blur(6px);
      display:flex; align-items:center; justify-content:center;
      padding:24px;
      animation:obFadeIn 0.3s ease;
    `;

    const dots = _steps.map((_, i) => `
      <div style="
        width:${i === _current ? 20 : 8}px; height:8px;
        border-radius:4px;
        background:${i === _current ? 'var(--accent)' : 'var(--border)'};
        transition:all 0.3s;
      "></div>
    `).join('');

    _overlay.innerHTML = `
      <style>
        @keyframes obFadeIn {
          from { opacity:0; transform:scale(0.95); }
          to   { opacity:1; transform:scale(1); }
        }
      </style>
      <div style="
        width:100%; max-width:360px;
        background:var(--bg-dark);
        border:1px solid var(--border-bright);
        border-radius:20px;
        padding:28px 24px 24px;
        text-align:center;
        box-shadow:0 0 60px rgba(212,118,78,0.2);
      ">
        <div style="font-size:56px;margin-bottom:16px">${step.icon}</div>
        <div style="font-size:20px;font-weight:800;color:var(--text-primary);margin-bottom:10px">
          ${step.title}
        </div>
        <div style="font-size:14px;color:var(--text-secondary);line-height:1.65;margin-bottom:24px">
          ${step.text}
        </div>

        <div style="display:flex;justify-content:center;gap:6px;margin-bottom:24px">
          ${dots}
        </div>

        <div style="display:flex;gap:10px">
          <button id="ob-skip" style="
            flex:1; padding:12px;
            background:transparent; border:1px solid var(--border);
            border-radius:10px; color:var(--text-secondary);
            font-size:13px; cursor:pointer; font-family:inherit;
          ">Пропустить</button>
          <button id="ob-next" style="
            flex:2; padding:12px;
            background:var(--accent); border:none;
            border-radius:10px; color:var(--bg-dark);
            font-size:15px; font-weight:700; cursor:pointer; font-family:inherit;
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
    localStorage.setItem(SEEN_KEY, '1');
    if (_overlay) {
      _overlay.style.opacity    = '0';
      _overlay.style.transition = 'opacity 0.3s';
      setTimeout(() => { _overlay?.remove(); _overlay = null; }, 300);
    }
    if (!_regulation && typeof Mascot !== 'undefined') {
      setTimeout(() => Mascot.say('welcome'), 500);
    }
  }

  // Сброс для повторного показа (для тестирования)
  function reset() {
    localStorage.removeItem(SEEN_KEY);
  }

  return { maybeShow, reset };
})();
