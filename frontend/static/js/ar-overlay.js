/**
 * FirstShift AR Overlay
 *
 * Рисует поверх видео:
 * - ArUco маркеры: точный полигон + метка + расстояние
 * - YOLOv8 объекты: bounding box + confidence
 * - 🎯 бейдж когда найдена цель активного квеста
 * - Пульсирующая стрелка к цели квеста когда маркер не в кадре
 * - Сканирующий прицел
 */

const AROverlay = (() => {
  let _canvas = null;
  let _ctx    = null;
  let _animFrame = null;

  let _detections     = [];
  let _displayDetections = [];
  let _scanAngle  = 0;
  let _scanPulse  = 0;
  let _targetFoundTime = 0;

  let _activeQuestTargetId    = null;
  let _activeQuestTargetClass = null;

  // Последнее известное направление к цели квеста
  // { direction_x, direction_y, ts } — обновляется когда маркер виден
  let _lastQuestDirection = null;

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
    const w   = _canvas.width;
    const h   = _canvas.height;
    const ctx = _ctx;
    const now = performance.now();

    ctx.clearRect(0, 0, w, h);
    _scanPulse += 0.04;
    _scanAngle += 0.012;

    const hasDetections = _detections.length > 0;
    _drawScanCrosshair(w, h, hasDetections ? 0.15 : 0.5);
    _updateDisplayDetections(now);

    // Проверяем видна ли цель квеста прямо сейчас
    const questTargetVisible = _displayDetections.some(d => _isQuestTarget(d));

    _displayDetections.forEach(det => {
      const isTarget = _isQuestTarget(det);
      if (det.type === 'marker' && det.corners) {
        _drawMarkerPolygon(det, isTarget);
      } else {
        _drawBoundingBox(det, isTarget);
      }
      if (isTarget) {
        _targetFoundTime = now;
        // Запоминаем направление пока маркер виден
        if (det.direction_x !== undefined) {
          _lastQuestDirection = {
            x:  det.direction_x,
            y:  det.direction_y ?? 0,
            ts: now,
          };
        }
      }
    });

    // Вспышка при нахождении цели
    if (now - _targetFoundTime < 400) {
      const alpha = 0.15 * (1 - (now - _targetFoundTime) / 400);
      ctx.fillStyle = `rgba(0,255,136,${alpha})`;
      ctx.fillRect(0, 0, w, h);
    }

    // Стрелка навигации — только если:
    // 1. Есть активный квест с маркером
    // 2. Маркер НЕ виден прямо сейчас
    // 3. Есть последнее известное направление (не старше 30 сек)
    if (
      _activeQuestTargetId !== null &&
      !questTargetVisible &&
      _lastQuestDirection &&
      now - _lastQuestDirection.ts < 30_000
    ) {
      _drawNavigationArrow(w, h, _lastQuestDirection.x, _lastQuestDirection.y, now);
    }
  }

  // ──────────────────────────────────────────────────────────────
  // Стрелка навигации к маркеру квеста
  // ──────────────────────────────────────────────────────────────
  function _drawNavigationArrow(w, h, dirX, dirY, now) {
    const ctx  = _ctx;
    const pulse = 0.6 + 0.4 * Math.sin(now / 300);
    const pad  = 24;

    // Определяем позицию стрелки по краю экрана
    let ax, ay, angle;

    const absX = Math.abs(dirX);
    const absY = Math.abs(dirY);

    if (absX >= absY) {
      // Лево / право
      ax    = dirX < 0 ? pad + 10 : w - pad - 10;
      ay    = h / 2;
      angle = dirX < 0 ? Math.PI : 0;
    } else {
      // Верх / низ
      ax    = w / 2;
      ay    = dirY < 0 ? pad + 10 : h - pad - 10;
      angle = dirY < 0 ? -Math.PI / 2 : Math.PI / 2;
    }

    ctx.save();
    ctx.globalAlpha = pulse * 0.9;
    ctx.translate(ax, ay);
    ctx.rotate(angle);

    // Фоновый кружок
    ctx.beginPath();
    ctx.arc(0, 0, 22, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0,255,136,0.18)';
    ctx.fill();
    ctx.strokeStyle = '#00ff88';
    ctx.lineWidth = 2;
    ctx.shadowColor = '#00ff88';
    ctx.shadowBlur  = 12;
    ctx.stroke();

    // Стрелка →
    ctx.strokeStyle = '#00ff88';
    ctx.lineWidth   = 2.5;
    ctx.lineCap     = 'round';
    ctx.lineJoin    = 'round';
    ctx.beginPath();
    ctx.moveTo(-8, 0);
    ctx.lineTo(8,  0);
    ctx.moveTo(2, -6);
    ctx.lineTo(8,  0);
    ctx.lineTo(2,  6);
    ctx.stroke();

    ctx.restore();

    // Подпись под стрелкой
    ctx.save();
    ctx.globalAlpha = pulse * 0.8;
    ctx.font        = 'bold 11px Consolas, monospace';
    ctx.fillStyle   = '#00ff88';
    ctx.textAlign   = 'center';
    ctx.shadowColor = '#00ff88';
    ctx.shadowBlur  = 6;

    const labelX = ax;
    const labelY = dirY > 0 ? ay - 30 : ay + 42;
    ctx.fillText('ЦЕЛЬ', labelX, labelY);
    ctx.restore();
  }

  // ──────────────────────────────────────────────────────────────
  // Сканирующий прицел
  // ──────────────────────────────────────────────────────────────
  function _drawScanCrosshair(w, h, alpha) {
    const ctx  = _ctx;
    const cx   = w / 2;
    const cy   = h / 2;
    const size = Math.min(w, h) * 0.18;
    const len  = size * 0.35;

    ctx.save();
    ctx.globalAlpha = alpha * (0.7 + 0.3 * Math.sin(_scanPulse));
    ctx.strokeStyle = '#00aaff';
    ctx.lineWidth   = 1.5;

    [[-1,-1],[1,-1],[1,1],[-1,1]].forEach(([dx, dy]) => {
      const x = cx + dx * size;
      const y = cy + dy * size;
      ctx.beginPath();
      ctx.moveTo(x + dx * -len, y);
      ctx.lineTo(x, y);
      ctx.lineTo(x, y + dy * -len);
      ctx.stroke();
    });

    ctx.globalAlpha = alpha * 0.4;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(_scanAngle) * size * 1.3, cy + Math.sin(_scanAngle) * size * 1.3);
    ctx.stroke();

    ctx.globalAlpha = alpha * 0.8;
    ctx.beginPath();
    ctx.arc(cx, cy, 3, 0, Math.PI * 2);
    ctx.stroke();

    ctx.restore();
  }

  // ──────────────────────────────────────────────────────────────
  // Полигон ArUco маркера
  // ──────────────────────────────────────────────────────────────
  function _drawMarkerPolygon(det, isTarget) {
    const ctx   = _ctx;
    const w     = _canvas.width;
    const h     = _canvas.height;
    const alpha = det._alpha || 1;
    const pts   = det.corners.map(([nx, ny]) => [nx * w, ny * h]);
    const color = isTarget ? '#00ff88' : '#00ffaa';
    const pulse = isTarget ? 0.4 + 0.4 * Math.sin(_scanPulse * 3) : 0;

    ctx.save();
    ctx.globalAlpha = alpha;

    // Заливка
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    pts.slice(1).forEach(([x, y]) => ctx.lineTo(x, y));
    ctx.closePath();
    ctx.fillStyle = `rgba(0,255,136,${0.08 + pulse * 0.1})`;
    ctx.fill();

    // Обводка
    ctx.strokeStyle = color;
    ctx.lineWidth   = isTarget ? 2.5 : 2;
    ctx.shadowColor = color;
    ctx.shadowBlur  = isTarget ? 12 : 6;
    ctx.stroke();

    // Угловые точки
    pts.forEach(([x, y]) => {
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
    });

    const cx     = pts.reduce((s, [x]) => s + x, 0) / 4;
    const cy     = pts.reduce((s, [,y]) => s + y, 0) / 4;
    const bboxTop = Math.min(...pts.map(([,y]) => y));

    // Расстояние над маркером
    if (det.distance_cm) {
      _drawDistanceBadge(cx, bboxTop - 36, det.distance_cm, color, alpha);
    }

    _drawLabel(cx, bboxTop - 8, det.label, color, isTarget, alpha);

    ctx.restore();
  }

  // ──────────────────────────────────────────────────────────────
  // Бейдж расстояния
  // ──────────────────────────────────────────────────────────────
  function _drawDistanceBadge(cx, y, distanceCm, color, alpha) {
    const ctx = _ctx;
    const distM = (distanceCm / 100).toFixed(1);
    const text  = `📍 ${distM} м`;

    ctx.save();
    ctx.globalAlpha = alpha * 0.92;
    ctx.font        = 'bold 12px Consolas, monospace';

    const tw = ctx.measureText(text).width;
    const px = cx - tw / 2 - 10;
    const py = y - 18;

    // Фон
    ctx.fillStyle = 'rgba(7,11,20,0.75)';
    _roundRect(ctx, px, py, tw + 20, 20, 10);
    ctx.fill();

    // Рамка
    ctx.strokeStyle = color;
    ctx.lineWidth   = 1;
    ctx.globalAlpha = alpha * 0.5;
    ctx.stroke();

    // Текст
    ctx.globalAlpha = alpha;
    ctx.fillStyle   = color;
    ctx.fillText(text, px + 10, py + 14);

    ctx.restore();
  }

  // ──────────────────────────────────────────────────────────────
  // Bounding box YOLOv8
  // ──────────────────────────────────────────────────────────────
  function _drawBoundingBox(det, isTarget) {
    const ctx   = _ctx;
    const w     = _canvas.width;
    const h     = _canvas.height;
    const alpha = det._alpha || 1;
    const px    = det.bbox.x * w;
    const py    = det.bbox.y * h;
    const pw    = det.bbox.w * w;
    const ph    = det.bbox.h * h;
    const color = isTarget ? '#00ff88' : (det.color || '#ffaa00');

    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.shadowColor = color;
    ctx.shadowBlur  = isTarget ? 12 : 6;
    ctx.strokeStyle = color;
    ctx.lineWidth   = isTarget ? 2.5 : 2;
    ctx.strokeRect(px, py, pw, ph);

    const cs = Math.min(pw, ph) * 0.2;
    [[px, py, cs, cs],[px+pw, py, -cs, cs],[px, py+ph, cs, -cs],[px+pw, py+ph, -cs, -cs]]
      .forEach(([bx, by, dx, dy]) => {
        ctx.beginPath();
        ctx.moveTo(bx+dx, by); ctx.lineTo(bx, by); ctx.lineTo(bx, by+dy);
        ctx.stroke();
      });

    ctx.fillStyle = `rgba(${_hexToRgb(color)},0.06)`;
    ctx.fillRect(px, py, pw, ph);

    _drawLabel(px + pw/2, py - 8, det.label, color, isTarget, alpha, det.confidence);
    ctx.restore();
  }

  // ──────────────────────────────────────────────────────────────
  // Лейбл
  // ──────────────────────────────────────────────────────────────
  function _drawLabel(cx, y, text, color, isTarget, alpha, confidence) {
    const ctx   = _ctx;
    let label   = text;
    if (confidence) label += ` ${Math.round(confidence * 100)}%`;
    if (isTarget)   label  = `🎯 ЦЕЛЬ: ${label}`;

    ctx.font = `bold ${isTarget ? 14 : 12}px Consolas, monospace`;
    const tw = ctx.measureText(label).width;
    const px = cx - tw / 2 - 8;
    const py = y - 20;

    ctx.fillStyle   = isTarget ? '#00ff88' : color;
    ctx.globalAlpha = alpha * 0.9;
    _roundRect(ctx, px, py, tw + 16, 20, 4);
    ctx.fill();

    ctx.fillStyle   = '#070b14';
    ctx.globalAlpha = alpha;
    ctx.fillText(label, px + 8, py + 14);
  }

  // ──────────────────────────────────────────────────────────────
  // Вспомогательные
  // ──────────────────────────────────────────────────────────────
  function _roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x+r, y);
    ctx.lineTo(x+w-r, y); ctx.arcTo(x+w, y, x+w, y+r, r);
    ctx.lineTo(x+w, y+h-r); ctx.arcTo(x+w, y+h, x+w-r, y+h, r);
    ctx.lineTo(x+r, y+h); ctx.arcTo(x, y+h, x, y+h-r, r);
    ctx.lineTo(x, y+r); ctx.arcTo(x, y, x+r, y, r);
    ctx.closePath();
  }

  function _hexToRgb(hex) {
    return `${parseInt(hex.slice(1,3),16)},${parseInt(hex.slice(3,5),16)},${parseInt(hex.slice(5,7),16)}`;
  }

  function _updateDisplayDetections(now) {
    const newKeys = new Set(_detections.map(_detKey));
    const oldKeys = new Set(_displayDetections.map(d => d._key));

    _displayDetections = _displayDetections.map(d => {
      if (newKeys.has(d._key)) {
        const fresh = _detections.find(nd => _detKey(nd) === d._key);
        return { ...fresh, _key: d._key, _alpha: Math.min(1, d._alpha + 0.15) };
      }
      return { ...d, _alpha: d._alpha - 0.08 };
    }).filter(d => d._alpha > 0);

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

  function _isQuestTarget(det) {
    if (_activeQuestTargetId !== null && det.type === 'marker')
      return det.marker_id === _activeQuestTargetId;
    if (_activeQuestTargetClass && det.detected_class)
      return det.detected_class === _activeQuestTargetClass;
    return false;
  }

  // ──────────────────────────────────────────────────────────────
  // Публичный API
  // ──────────────────────────────────────────────────────────────
  function updateDetections(detections) {
    _detections = detections || [];
    const q = (typeof QuestEngine !== 'undefined') ? QuestEngine.getActive() : null;
    _activeQuestTargetId    = q?.target_marker_id ?? null;
    _activeQuestTargetClass = q?.target_class     ?? null;

    // Если цели нет — сбрасываем направление
    if (!q) _lastQuestDirection = null;
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
