/**
 * CASPER AR Overlay — шаг 6
 *
 * Рисует поверх видео:
 * - ArUco маркеры: точный полигон по 4 углам + метка объекта
 * - YOLOv8 объекты: bounding box + confidence
 * - «🎯 ЦЕЛЬ!» бейдж когда найдена цель активного квеста
 * - Сканирующая анимация когда нет детекций
 * - Fade in/out при появлении/исчезновении объектов
 */

const AROverlay = (() => {
  let _canvas = null;
  let _ctx = null;
  let _animFrame = null;
  let _detections = [];
  let _prevDetections = [];
  let _scanAngle = 0;
  let _scanPulse = 0;
  let _targetFoundTime = 0;    // время последнего совпадения с квестом
  let _activeQuestTargetId = null;
  let _activeQuestTargetClass = null;

  // Плавное исчезновение боксов
  let _displayDetections = [];  // с alpha для fade
  const FADE_MS = 600;

  function init(canvas) {
    _canvas = canvas;
    _ctx = canvas.getContext('2d');
    _resize();
    window.addEventListener('resize', _resize);
    _loop();
  }

  function _resize() {
    if (!_canvas) return;
    _canvas.width  = _canvas.offsetWidth;
    _canvas.height = _canvas.offsetHeight;
  }

  function _loop() {
    _animFrame = requestAnimationFrame(_loop);
    _render();
  }

  function _render() {
    const w = _canvas.width;
    const h = _canvas.height;
    const ctx = _ctx;
    const now = performance.now();

    ctx.clearRect(0, 0, w, h);

    _scanPulse += 0.04;
    _scanAngle += 0.012;

    const hasDetections = _detections.length > 0;

    // ---- Сканирующая анимация (тише если есть детекции) ----
    const scanAlpha = hasDetections ? 0.15 : 0.5;
    _drawScanCrosshair(w, h, scanAlpha);

    // ---- Обновляем fade для детекций ----
    _updateDisplayDetections(now);

    // ---- Рисуем детекции ----
    _displayDetections.forEach(det => {
      const isTarget = _isQuestTarget(det);
      if (det.type === 'marker' && det.corners) {
        _drawMarkerPolygon(det, isTarget);
      } else {
        _drawBoundingBox(det, isTarget);
      }
      if (isTarget) _targetFoundTime = now;
    });

    // ---- Вспышка «цель найдена» ----
    if (now - _targetFoundTime < 400) {
      const alpha = 0.15 * (1 - (now - _targetFoundTime) / 400);
      ctx.fillStyle = `rgba(0,255,136,${alpha})`;
      ctx.fillRect(0, 0, w, h);
    }
  }

  // ---- Сканирующий прицел ----
  function _drawScanCrosshair(w, h, alpha) {
    const ctx = _ctx;
    const cx = w / 2;
    const cy = h / 2;
    const size = Math.min(w, h) * 0.18;
    const len = size * 0.35;

    ctx.save();
    ctx.globalAlpha = alpha * (0.7 + 0.3 * Math.sin(_scanPulse));
    ctx.strokeStyle = '#00aaff';
    ctx.lineWidth = 1.5;

    // Угловые скобки
    [[-1,-1],[1,-1],[1,1],[-1,1]].forEach(([dx, dy]) => {
      const x = cx + dx * size;
      const y = cy + dy * size;
      ctx.beginPath();
      ctx.moveTo(x + dx * -len, y);
      ctx.lineTo(x, y);
      ctx.lineTo(x, y + dy * -len);
      ctx.stroke();
    });

    // Радар
    ctx.globalAlpha = alpha * 0.4;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(
      cx + Math.cos(_scanAngle) * size * 1.3,
      cy + Math.sin(_scanAngle) * size * 1.3,
    );
    ctx.stroke();

    // Центральная точка
    ctx.globalAlpha = alpha * 0.8;
    ctx.beginPath();
    ctx.arc(cx, cy, 3, 0, Math.PI * 2);
    ctx.stroke();

    ctx.restore();
  }

  // ---- Полигон ArUco маркера (по 4 углам) ----
  function _drawMarkerPolygon(det, isTarget) {
    const ctx = _ctx;
    const w = _canvas.width;
    const h = _canvas.height;
    const alpha = det._alpha || 1;

    // Нормализованные углы → пиксели
    const pts = det.corners.map(([nx, ny]) => [nx * w, ny * h]);

    const color = isTarget ? '#00ff88' : '#00ffaa';
    const pulse = isTarget ? 0.4 + 0.4 * Math.sin(_scanPulse * 3) : 0;

    ctx.save();
    ctx.globalAlpha = alpha;

    // Заливка полигона
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    pts.slice(1).forEach(([x, y]) => ctx.lineTo(x, y));
    ctx.closePath();
    ctx.fillStyle = `rgba(0,255,136,${0.08 + pulse * 0.1})`;
    ctx.fill();

    // Обводка
    ctx.strokeStyle = color;
    ctx.lineWidth = isTarget ? 2.5 : 2;
    ctx.shadowColor = color;
    ctx.shadowBlur = isTarget ? 12 : 6;
    ctx.stroke();

    // Угловые маркеры
    pts.forEach(([x, y]) => {
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
    });

    // Центр маркера — для лейбла
    const cx = pts.reduce((s, [x]) => s + x, 0) / 4;
    const cy = pts.reduce((s, [,y]) => s + y, 0) / 4;
    const bboxTop = Math.min(...pts.map(([,y]) => y));

    _drawLabel(cx, bboxTop - 8, det.label, color, isTarget, alpha);

    ctx.restore();
  }

  // ---- Bounding box YOLOv8 объекта ----
  function _drawBoundingBox(det, isTarget) {
    const ctx = _ctx;
    const w = _canvas.width;
    const h = _canvas.height;
    const alpha = det._alpha || 1;

    const px = det.bbox.x * w;
    const py = det.bbox.y * h;
    const pw = det.bbox.w * w;
    const ph = det.bbox.h * h;

    const color = isTarget ? '#00ff88' : (det.color || '#ffaa00');

    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.shadowColor = color;
    ctx.shadowBlur = isTarget ? 12 : 6;
    ctx.strokeStyle = color;
    ctx.lineWidth = isTarget ? 2.5 : 2;

    // Основной бокс
    ctx.strokeRect(px, py, pw, ph);

    // Угловые скобки
    const cs = Math.min(pw, ph) * 0.2;
    [
      [px,      py,      cs,  cs],
      [px + pw, py,      -cs, cs],
      [px,      py + ph, cs,  -cs],
      [px + pw, py + ph, -cs, -cs],
    ].forEach(([bx, by, dx, dy]) => {
      ctx.beginPath();
      ctx.moveTo(bx + dx, by);
      ctx.lineTo(bx, by);
      ctx.lineTo(bx, by + dy);
      ctx.stroke();
    });

    // Лёгкая заливка
    ctx.fillStyle = `rgba(${_hexToRgb(color)},0.06)`;
    ctx.fillRect(px, py, pw, ph);

    _drawLabel(px + pw / 2, py - 8, det.label, color, isTarget, alpha, det.confidence);

    ctx.restore();
  }

  // ---- Лейбл над боксом ----
  function _drawLabel(cx, y, text, color, isTarget, alpha, confidence) {
    const ctx = _ctx;

    let label = text;
    if (confidence) label += ` ${Math.round(confidence * 100)}%`;
    if (isTarget) label = `🎯 ЦЕЛЬ: ${label}`;

    ctx.font = `bold ${isTarget ? 14 : 12}px Consolas, monospace`;
    const tw = ctx.measureText(label).width;
    const px = cx - tw / 2 - 8;
    const py = y - 20;

    // Фон лейбла
    ctx.fillStyle = isTarget ? '#00ff88' : color;
    ctx.globalAlpha = alpha * 0.9;
    _roundRect(ctx, px, py, tw + 16, 20, 4);
    ctx.fill();

    // Текст
    ctx.fillStyle = '#070b14';
    ctx.globalAlpha = alpha;
    ctx.fillText(label, px + 8, py + 14);
  }

  function _roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.arcTo(x + w, y, x + w, y + r, r);
    ctx.lineTo(x + w, y + h - r);
    ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
    ctx.lineTo(x + r, y + h);
    ctx.arcTo(x, y + h, x, y + h - r, r);
    ctx.lineTo(x, y + r);
    ctx.arcTo(x, y, x + r, y, r);
    ctx.closePath();
  }

  function _hexToRgb(hex) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `${r},${g},${b}`;
  }

  // ---- Fade in/out детекций ----
  function _updateDisplayDetections(now) {
    // Добавляем новые с alpha=0 (fade in)
    const newKeys = new Set(_detections.map(_detKey));
    const oldKeys = new Set(_displayDetections.map(d => d._key));

    // Обновляем существующие
    _displayDetections = _displayDetections.map(d => {
      if (newKeys.has(d._key)) {
        return { ..._detections.find(nd => _detKey(nd) === d._key), _key: d._key, _alpha: Math.min(1, d._alpha + 0.15) };
      } else {
        return { ...d, _alpha: d._alpha - 0.08 };  // fade out
      }
    }).filter(d => d._alpha > 0);

    // Добавляем совсем новые
    _detections.forEach(det => {
      const key = _detKey(det);
      if (!oldKeys.has(key)) {
        _displayDetections.push({ ...det, _key: key, _alpha: 0.1 });
      }
    });
  }

  function _detKey(det) {
    if (det.type === 'marker') return `m_${det.marker_id}`;
    return `o_${det.detected_class}_${Math.round((det.bbox?.x || 0) * 10)}`;
  }

  // ---- Проверка совпадения с квестом ----
  function _isQuestTarget(det) {
    if (_activeQuestTargetId !== null && det.type === 'marker') {
      return det.marker_id === _activeQuestTargetId;
    }
    if (_activeQuestTargetClass && det.detected_class) {
      return det.detected_class === _activeQuestTargetClass;
    }
    return false;
  }

  // ---- Публичный API ----

  function updateDetections(detections) {
    _detections = detections || [];

    // Синхронизируем цель квеста
    const q = (typeof QuestEngine !== 'undefined') ? QuestEngine.getActive() : null;
    _activeQuestTargetId    = q?.target_marker_id ?? null;
    _activeQuestTargetClass = q?.target_class ?? null;
  }

  function flashSuccess() {
    _targetFoundTime = performance.now();
  }

  function stop() {
    if (_animFrame) cancelAnimationFrame(_animFrame);
    window.removeEventListener('resize', _resize);
  }

  return { init, updateDetections, flashSuccess, stop };
})();
