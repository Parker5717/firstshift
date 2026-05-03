/**
 * CASPER API Client
 * Обёртка над fetch с JWT-авторизацией.
 * Все методы возвращают промис с данными или бросают Error.
 */

const API = (() => {
  const BASE = '';  // same-origin, сервер FastAPI отдаёт и фронт и API
  const TOKEN_KEY = 'casper_token';

  let _token = sessionStorage.getItem(TOKEN_KEY);

  // ---------- Токен ----------

  function setToken(token) {
    _token = token;
    sessionStorage.setItem(TOKEN_KEY, token);
  }

  function clearToken() {
    _token = null;
    sessionStorage.removeItem(TOKEN_KEY);
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
      clearToken();
      window.location.href = '/';
      throw new Error('Сессия истекла, войди заново');
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

  // ---------- Методы ----------

  async function login(username) {
    const data = await post('/api/auth/login', { username });
    setToken(data.access_token);
    return data;  // { access_token, user }
  }

  async function getProfile() {
    return get('/api/users/me');
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
    get,
    post,
    getProfile,
    getQuests,
    startQuest,
    completeQuest,
    getLeaderboard,
  };
})();
