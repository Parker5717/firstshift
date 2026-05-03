/**
 * CASPER Camera Manager
 * Управляет видеопотоком через getUserMedia.
 * Поддерживает переключение между фронтальной и задней камерой.
 */

const Camera = (() => {
  let _stream = null;
  let _facingMode = 'environment';  // 'environment' = задняя, 'user' = фронтальная
  let _videoEl = null;

  /**
   * Запустить камеру и показать поток в videoEl.
   * @param {HTMLVideoElement} videoEl
   * @param {'environment'|'user'} facingMode
   */
  async function start(videoEl, facingMode = 'environment') {
    _videoEl = videoEl;
    _facingMode = facingMode;

    // Если поток уже есть — останови старый
    if (_stream) stop();

    const constraints = {
      video: {
        facingMode: { ideal: _facingMode },
        width:  { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    };

    try {
      _stream = await navigator.mediaDevices.getUserMedia(constraints);
      videoEl.srcObject = _stream;
      await videoEl.play();
      return true;
    } catch (err) {
      console.error('[Camera] Ошибка доступа к камере:', err);
      return false;
    }
  }

  /**
   * Переключить камеру (фронт ↔ тыл).
   * @returns {'environment'|'user'} новый режим
   */
  async function toggle() {
    _facingMode = _facingMode === 'environment' ? 'user' : 'environment';
    if (_videoEl) await start(_videoEl, _facingMode);
    return _facingMode;
  }

  /**
   * Остановить поток и освободить камеру.
   */
  function stop() {
    if (_stream) {
      _stream.getTracks().forEach(track => track.stop());
      _stream = null;
    }
    if (_videoEl) _videoEl.srcObject = null;
  }

  /**
   * Текущий режим камеры.
   */
  function getFacingMode() {
    return _facingMode;
  }

  /**
   * Доступна ли вообще камера в браузере.
   */
  function isSupported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  }

  /**
   * Получить текущий HTMLVideoElement.
   */
  function getVideo() {
    return _videoEl;
  }

  return { start, toggle, stop, getFacingMode, isSupported, getVideo };
})();
