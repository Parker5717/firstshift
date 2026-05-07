/**
 * FirstShift API Client
 * Обёртка над fetch с JWT-авторизацией.
 * Все методы возвращают промис с данными или бросают Error.
 */

const API = (() => {
  const BASE        = '';  // same-origin, сервер FastAPI отдаёт и фронт и API
  const TOKEN_KEY   = 'firstshift_token';
  const PROFILE_KEY = 'firstshift_profile';

  let _token = sessionStorage.getItem(TOKEN_KEY);

  // ---------- Токен ----------

  function setToken(token) {
    _token = token;
    sessionStorage.setItem(TOKEN_KEY, token);
  }

  function clearToken() {
    _token = null;
    sessionStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(PROFILE_KEY);
  }

  function hasToken() {
    return !!_token;
  }

  // ---------- Базовый fetch ----------

  async function _fetch(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (_token) headers['Authorization'] = `Bearer ${_token}`;

    const resp = await fetch(BASE + path, { ...options, headers });

    if (resp.status === 401) {
      // На auth-эндпоинтах 401 = неверные данные, редирект не нужен
      if (!path.startsWith('/api/auth/')) {
        clearToken();
        window.location.href = '/';
      }
      let detail = 'Сессия истекла, войди заново';
      try { detail = (await resp.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }

    if (!resp.ok) {
      let detail = `HTTP ${resp.status}`;
      try { detail = (await resp.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }

    return resp.json();
  }

  async function post(path, data) {
    return _fetch(path, { method: 'POST', body: JSON.stringify(data) });
  }

  async function get(path) {
    return _fetch(path, { method: 'GET' });
  }

  async function patch(path, data) {
    return _fetch(path, { method: 'PATCH', body: JSON.stringify(data) });
  }

  // ---------- Методы ----------

  async function login(username, password) {
    const data = await post('/api/auth/login', { username, password });
    setToken(data.access_token);
    if (data.user) localStorage.setItem(PROFILE_KEY, JSON.stringify(data.user));
    return data;  // { access_token, user }
  }

  async function register(username, password, displayName, privacyAccepted = false, birthYear = null, companyCode = '') {
    const data = await post('/api/auth/register', {
      username,
      password,
      display_name: displayName || null,
      privacy_accepted: privacyAccepted,
      birth_year: birthYear,
      company_code: companyCode,
    });
    setToken(data.access_token);
    if (data.user) localStorage.setItem(PROFILE_KEY, JSON.stringify(data.user));
    return data;
  }

  // Профиль кешируется в localStorage — один запрос за сессию, работает между вкладками.
  // forceRefresh=true пробивает кеш (например, после смены имени).
  async function getProfile(forceRefresh = false) {
    if (!forceRefresh) {
      const cached = localStorage.getItem(PROFILE_KEY);
      if (cached) {
        try { return JSON.parse(cached); } catch (_) {}
      }
    }
    const profile = await get('/api/users/me');
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    return profile;
  }

  async function updateDisplayName(name) {
    return patch('/api/users/me/display-name', { display_name: name });
  }

  async function updateProfile(displayName) {
    const profile = await _fetch('/api/users/me', {
      method: 'PATCH',
      body: JSON.stringify({ display_name: displayName }),
    });
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    return profile;
  }

  async function getQuests() {
    return get('/api/quests');
  }

  async function startQuest(slug) {
    return post(`/api/quests/${slug}/start`, {});
  }

  async function completeQuest(slug) {
    return post(`/api/quests/${slug}/complete`, {});
  }

  async function getLeaderboard() {
    return get('/api/users/leaderboard');
  }

  return {
    hasToken,
    clearToken,
    login,
    register,
    get,
    post,
    patch,
    getProfile,
    updateDisplayName,
    updateProfile,
    getQuests,
    startQuest,
    completeQuest,
    getLeaderboard,
  };
})();
