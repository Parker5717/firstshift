/**
 * CASPER Quiz
 * Показывает вопрос с вариантами ответов для квестов типа knowledge.
 * Вызывается перед завершением квеста — если ответ правильный, квест засчитывается.
 */

const Quiz = (() => {

  /**
   * Показать квиз для квеста.
   * @param {object} quest — объект квеста с params_json
   * @returns {Promise<boolean>} — true если ответ правильный
   */
  function show(quest) {
    return new Promise((resolve) => {
      let params = {};
      try { params = JSON.parse(quest.params_json || '{}'); } catch (_) {}

      const quiz = params.quiz;
      if (!quiz) { resolve(true); return; }  // нет квиза — сразу засчитываем

      const { question, options, correct_index } = quiz;
      let _answered = false;

      const overlay = document.createElement('div');
      overlay.style.cssText = `
        position:fixed; inset:0; z-index:90;
        background:rgba(7,11,20,0.92);
        backdrop-filter:blur(6px);
        display:flex; align-items:center; justify-content:center;
        padding:20px;
        animation:fadeIn 0.3s ease;
      `;

      overlay.innerHTML = `
        <style>
          @keyframes fadeIn { from{opacity:0;transform:scale(0.95)} to{opacity:1;transform:scale(1)} }
          .quiz-option {
            width:100%; padding:14px 16px; margin-bottom:10px;
            background:var(--bg-glass); border:1px solid var(--border);
            border-radius:10px; color:var(--text-primary);
            font-size:14px; line-height:1.5; cursor:pointer;
            text-align:left; transition:all 0.2s; font-family:var(--font-main);
          }
          .quiz-option:hover { border-color:var(--accent); background:var(--accent-glow); }
          .quiz-option.correct { border-color:var(--success)!important; background:rgba(0,255,136,0.12)!important; color:var(--success); }
          .quiz-option.wrong   { border-color:var(--danger)!important;  background:rgba(255,51,85,0.12)!important;  color:var(--danger); }
          .quiz-option:disabled { cursor:default; }
        </style>
        <div style="
          width:100%; max-width:420px;
          background:var(--bg-dark);
          border:1px solid var(--border-bright);
          border-radius:20px; padding:28px 22px;
          box-shadow:0 0 60px rgba(0,170,255,0.15);
        ">
          <div style="font-size:11px;color:var(--accent);font-family:var(--font-mono);letter-spacing:1px;margin-bottom:12px">
            📋 ПРОВЕРКА ЗНАНИЙ
          </div>
          <div style="font-size:17px;font-weight:700;color:var(--text-primary);line-height:1.5;margin-bottom:20px">
            ${question}
          </div>
          <div id="quiz-options">
            ${options.map((opt, i) => `
              <button class="quiz-option" data-index="${i}">${opt}</button>
            `).join('')}
          </div>
          <div id="quiz-feedback" style="
            min-height:40px; text-align:center;
            font-size:14px; font-weight:700; margin-top:12px;
          "></div>
        </div>
      `;

      document.body.appendChild(overlay);

      // Обработка кликов по вариантам
      overlay.querySelectorAll('.quiz-option').forEach(btn => {
        btn.addEventListener('click', () => {
          if (_answered) return;
          _answered = true;

          const idx = parseInt(btn.dataset.index);
          const isCorrect = idx === correct_index;

          // Подсвечиваем все варианты
          overlay.querySelectorAll('.quiz-option').forEach((b, i) => {
            b.disabled = true;
            if (i === correct_index) b.classList.add('correct');
            else if (i === idx && !isCorrect) b.classList.add('wrong');
          });

          const feedback = document.getElementById('quiz-feedback');

          if (isCorrect) {
            feedback.style.color = 'var(--success)';
            feedback.textContent = '✅ Верно! Квест засчитан!';
            if (typeof Mascot !== 'undefined') Mascot.say('quest_complete');
            setTimeout(() => {
              overlay.remove();
              resolve(true);
            }, 1500);
          } else {
            feedback.style.color = 'var(--danger)';
            feedback.textContent = '❌ Неверно. Правильный ответ выделен зелёным.';
            if (typeof Mascot !== 'undefined') Mascot.onError();
            // Даём закрыть и попробовать снова
            setTimeout(() => {
              const retryBtn = document.createElement('button');
              retryBtn.style.cssText = `
                margin-top:10px; width:100%; padding:12px;
                background:transparent; border:1px solid var(--border);
                border-radius:10px; color:var(--text-secondary);
                font-size:13px; cursor:pointer; font-family:var(--font-main);
              `;
              retryBtn.textContent = 'Попробовать снова →';
              retryBtn.addEventListener('click', () => {
                overlay.remove();
                resolve(false);  // false = не засчитывать, дать попробовать снова
              });
              feedback.parentElement.appendChild(retryBtn);
            }, 1000);
          }
        });
      });
    });
  }

  return { show };
})();
