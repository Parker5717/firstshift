/**
 * CASPER Vision Client (WebSocket версия, шаг 5)
 *
 * Устанавливает постоянное WS-соединение с /ws/vision.
 * Отправляет кадры каждую секунду.
 * Получает детекции и обновляет AR-оверлей + квест-прогресс.
 *
 * Fallback: если WS недоступен — переключается на REST /api/vision/detect.
 */

const VisionClient = (() => {
  let _ws = null;
  let _intervalId = null;
  let _pingInterval = null;
  let _captureCanvas = null;
  let _ctx = null;
  let _videoEl = null;
  let _isPPEMode = false;
  let _isProcessing = false;
  let _useREST = false;

  const INTERVAL_MS   = 1000;
  const REST_INTERVAL = 1500;
  const JPEG_QUALITY  = 0.65;

  function init() {
    _captureCanvas = document.createElement('canvas');
    _ctx = _captureCanvas.getContext('2d');
  }

  function captureFrame(videoEl) {
    if (!videoEl || videoEl.readyState < 2) return null;
    const w = videoEl.videoWidth;
    const h = videoEl.videoHeight;
    if (!w || !h) return null;
    _captureCanvas.width  = w;
    _captureCanvas.height = h;
    _ctx.drawImage(videoEl, 0, 0, w, h);
    return _captureCanvas.toDataURL('image/jpeg', JPEG_QUALITY).split(',')[1];
  }

  function _connectWS() {
    const token = sessionStorage.getItem('casper_token');
    if (!token) return;

    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const url   = `${proto}://${location.host}/ws/vision?token=${token}`;
    _ws = new WebSocket(url);

    _ws.onopen = () => {
      console.log('[VisionClient] WS подключён');
      _useREST = false;
      if (_pingInterval) clearInterval(_pingInterval);
      _pingInterval = setInterval(() => {
        if (_ws && _ws.readyState === WebSocket.OPEN) {
          _ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, 15000);
    };

    _ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'detections') _handleDetections(data);
      } catch (e) {}
      _isProcessing = false;
    };

    _ws.onerror = () => {
      console.warn('[VisionClient] WS ошибка — переключаемся на REST');
      _useREST = true;
    };

    _ws.onclose = () => {
      _ws = null;
      if (_intervalId) setTimeout(_connectWS, 3000);
    };
  }

  async function _sendFrame() {
    if (!_videoEl || _isProcessing) return;
    const b64 = captureFrame(_videoEl);
    if (!b64) return;
    _isProcessing = true;

    if (!_useREST && _ws && _ws.readyState === WebSocket.OPEN) {
      _ws.send(JSON.stringify({
        type: 'frame', image: b64,
        run_ppe: _isPPEMode, run_objects: !_isPPEMode,
      }));
    } else {
      await _sendREST(b64);
      _isProcessing = false;
    }
  }

  async function _sendREST(b64) {
    try {
      const token = sessionStorage.getItem('casper_token');
      if (!token) return;
      const resp = await fetch('/api/vision/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ image: b64, run_ppe: _isPPEMode, run_objects: !_isPPEMode }),
      });
      if (resp.ok) _handleDetections(await resp.json());
    } catch (e) {
      console.debug('[VisionClient] REST ошибка:', e.message);
    }
  }

  // ---- Маппинг детекций → ID объектов в энциклопедии ----
  const DETECTION_TO_ENCYCLOPEDIA = {
    // marker_id → encyclopedia object id
    markers: {
      0: 'marker_0',
      1: 'marker_1',
      2: 'marker_2',
      3: 'marker_3',
      4: 'marker_4',
      10: 'ppe_helmet',
      11: 'ppe_vest',
    },
    // detected_class → encyclopedia object id
    objects: {
      'fire_extinguisher': 'marker_4',
    },
  };

  // Показанные подсказки — не спамим одним объектом
  const _encyclopediaShown = new Set();
  let _encyclopediaTimer = null;

  function _showEncyclopediaHint(det, dets = []) {
    let objId = null;
    if (det.type === 'marker') {
      objId = DETECTION_TO_ENCYCLOPEDIA.markers[det.marker_id];
    } else if (det.detected_class) {
      objId = DETECTION_TO_ENCYCLOPEDIA.objects[det.detected_class];
    }
    if (!objId || _encyclopediaShown.has(objId)) return;
    _encyclopediaShown.add(objId);

    // Убираем через 5 минут чтобы можно было снова показать
    setTimeout(() => _encyclopediaShown.delete(objId), 300000);

    // Показываем тост
    const existing = document.getElementById('enc-hint-toast');
    if (existing) existing.remove();
    clearTimeout(_encyclopediaTimer);

    const toast = document.createElement('div');
    toast.id = 'enc-hint-toast';
    toast.style.cssText = `
      position:fixed; bottom:200px; left:50%;
      transform:translateX(-50%) translateY(20px);
      background:rgba(7,11,20,0.95);
      border:1px solid #aa88ff;
      border-radius:12px; padding:12px 18px;
      display:flex; align-items:center; gap:10px;
      box-shadow:0 0 24px rgba(170,136,255,0.3);
      z-index:35; cursor:pointer; white-space:nowrap;
      opacity:0; transition:all 0.35s ease;
      max-width:90vw;
    `;
    toast.innerHTML = `
      <span style="font-size:20px">📖</span>
      <span style="font-size:13px;color:#cc99ff;font-weight:600">
        Узнай больше в энциклопедии →
      </span>
    `;
    toast.addEventListener('click', async () => {
      toast.remove();
      clearTimeout(_encyclopediaTimer);
      // Если есть активный квест на этот объект — засчитываем
      const activeQuest = QuestEngine.getActive();
      if (activeQuest) {
        const det = dets[0] || {};
        let matched = false;
        if (activeQuest.target_marker_id !== null && activeQuest.target_marker_id !== undefined) {
          matched = det.marker_id === activeQuest.target_marker_id;
        }
        if (!matched && activeQuest.target_class) {
          matched = det.detected_class === activeQuest.target_class;
        }
        if (matched) {
          await QuestEngine.complete(activeQuest.slug);
          try { XPBar.update(await API.getProfile()); } catch (_) {}
        }
      }
      // Открываем энциклопедию на нужном объекте
      window.location.href = `/encyclopedia?obj=${objId}`;
    });
    document.body.appendChild(toast);

    // Анимация появления
    setTimeout(() => {
      toast.style.opacity = '1';
      toast.style.transform = 'translateX(-50%) translateY(0)';
    }, 50);

    // Автоскрытие через 4 сек
    _encyclopediaTimer = setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(-50%) translateY(10px)';
      setTimeout(() => toast.remove(), 350);
    }, 4000);
  }

  function _handleDetections(data) {
    AROverlay.updateDetections(data.all_detections || []);
    if (_isPPEMode && data.ppe) { _updatePPEUI(data.ppe); return; }
    const dets = data.all_detections || [];

    // SpeedRun трекер — передаём все найденные маркеры
    if (typeof SpeedRun !== 'undefined' && SpeedRun.isActive()) {
      (data.markers || []).forEach(m => SpeedRun.onMarkerDetected(m.marker_id));
    }

    // Сервер автоматически завершил квесты — обновляем UI без ручной кнопки
    const autoCompleted = (data.quest_events || []).some(e => e.type === 'quest_complete');
    if (autoCompleted) {
      data.quest_events.forEach(evt => {
        if (evt.type !== 'quest_complete') return;
        console.log('[Quest] Автозавершён сервером:', evt.quest_slug, '+' + evt.xp_gained + ' XP');

        // Убираем ручную кнопку если висит
        document.getElementById('btn-complete-quest')?.remove();
        clearTimeout(_completeTimeout);

        // Показываем попап +XP, затем подтягиваем свежий профиль с сервера
        XPBar.showXPGain(evt.xp_gained, evt.leveled_up, evt.new_level, evt.level_title);
        API.getProfile().then(p => XPBar.update(p)).catch(() => {});

        // Перезагружаем квесты — разблокировались новые
        QuestEngine.load();

        // Показываем ачивки если разблокировались
        if (evt.newly_unlocked_achievements?.length > 0) {
          if (typeof Achievements !== 'undefined') Achievements.showUnlocked(evt.newly_unlocked_achievements);
        }
      });
    }

    if (dets.length > 0) {
      console.log('[Vision] Детекций:', dets.length,
        '| markers:', (data.markers||[]).map(m=>m.marker_id),
        '| objects:', (data.objects||[]).map(o=>o.detected_class));
      _showEncyclopediaHint(dets[0], dets);
      // Ручную кнопку показываем только если сервер не завершил квест сам
      if (!autoCompleted) _checkQuestProgress(data);
    }
  }

  function _checkQuestProgress(data) {
    const q = QuestEngine.getActive();
    if (!q) {
      console.log('[Quest] Нет активного квеста — начни квест через 🎯');
      return;
    }
    console.log('[Quest] Активный:', q.slug,
      '| target_marker_id:', q.target_marker_id,
      '| target_class:', q.target_class);

    let matched = false;
    if (q.target_marker_id !== null && q.target_marker_id !== undefined) {
      matched = (data.markers || []).some(m => m.marker_id === q.target_marker_id);
      console.log('[Quest] Маркер совпадение:', matched,
        '(ищем ID', q.target_marker_id, ', видим', (data.markers||[]).map(m=>m.marker_id), ')');
    }
    if (!matched && q.target_class) {
      matched = (data.objects || []).some(o => o.detected_class === q.target_class);
    }
    if (matched) {
      console.log('[Quest] ✅ СОВПАДЕНИЕ! Показываю кнопку завершения');
      _showCompleteButton(q);
    }
  }

  let _completeTimeout = null;
  function _showCompleteButton(quest) {
    let btn = document.getElementById('btn-complete-quest');
    if (!btn) {
      btn = document.createElement('button');
      btn.id = 'btn-complete-quest';
      btn.style.cssText = [
        'position:fixed', 'bottom:120px', 'left:50%',
        'transform:translateX(-50%)', 'padding:14px 28px',
        'background:#00ff88', 'color:#070b14', 'border:none',
        'border-radius:12px', 'font-size:16px', 'font-weight:800',
        'cursor:pointer', 'z-index:30',
        'box-shadow:0 0 30px rgba(0,255,136,0.5)', 'white-space:nowrap',
      ].join(';');
      document.body.appendChild(btn);
      btn.addEventListener('click', async () => {
        btn.remove();
        clearTimeout(_completeTimeout);

        // Для knowledge квестов — сначала показываем вопрос
        if (quest.type === 'knowledge' && typeof Quiz !== 'undefined') {
          const correct = await Quiz.show(quest);
          if (!correct) return;  // неверный ответ — не засчитываем
        }

        await QuestEngine.complete(quest.slug);
        try {
          const profile = await API.getProfile();
          XPBar.update(profile);
        } catch (_) {}
      });
    }
    btn.textContent = `✅ Засчитать «${quest.title}»!`;
    clearTimeout(_completeTimeout);
    _completeTimeout = setTimeout(() => {
      document.getElementById('btn-complete-quest')?.remove();
    }, 5000);
  }

  function _updatePPEUI(ppe) {
    const h = document.getElementById('ppe-helmet');
    const v = document.getElementById('ppe-vest');
    const s = document.getElementById('ppe-status');
    if (h) h.textContent = ppe.helmet ? '✅ Каска' : '❌ Каска';
    if (v) v.textContent = ppe.vest   ? '✅ Жилет' : '❌ Жилет';
    if (s) {
      s.textContent = ppe.all_ok ? 'Снаряжение в порядке!' : `Не хватает: ${ppe.missing.join(', ')}`;
      s.style.color = ppe.all_ok ? '#00ff88' : '#ff3355';
    }
    if (ppe.all_ok) {
      const q = QuestEngine.getActive();
      if (q && q.type === 'safety') _showCompleteButton(q);
    }
  }

  function start(videoEl, isPPEMode = false) {
    stop();
    _videoEl = videoEl;
    _isPPEMode = isPPEMode;
    _connectWS();
    _intervalId = setInterval(_sendFrame, isPPEMode ? REST_INTERVAL : INTERVAL_MS);
    console.log('[VisionClient] Запущен, режим:', isPPEMode ? 'PPE' : 'detection');
  }

  function stop() {
    if (_intervalId)  { clearInterval(_intervalId);  _intervalId  = null; }
    if (_pingInterval){ clearInterval(_pingInterval); _pingInterval = null; }
    if (_ws)          { _ws.close(); _ws = null; }
    _isProcessing = false;
    _videoEl = null;
  }

  return { init, start, stop, captureFrame };
})();
