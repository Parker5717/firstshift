/**
 * FirstShift API Client
 * Обёртка над fetch с JWT-авторизацией.
 */

const API = (() => {
  const BASE      = '';
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

  function hasToken() { return !!_token; }

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

  // ---------- Auth ----------

  async function login(username, password) {
    const data = await post('/api/auth/login', { username, password });
    setToken(data.access_token);
    return data;
  }

  async function register(username, password, displayName) {
    const data = await post('/api/auth/register', {
      username,
      password,
      display_name: displayName || null,
    });
    setToken(data.access_token);
    return data;
  }

  // ---------- Методы ----------

  async function getProfile()         { return get('/api/users/me'); }
  async function getQuests()          { return get('/api/quests'); }
  async function startQuest(slug)     { return post(`/api/quests/${slug}/start`, {}); }
  async function completeQuest(slug)  { return post(`/api/quests/${slug}/complete`, {}); }
  async function getLeaderboard()     { return get('/api/users/leaderboard'); }

  return {
    hasToken, clearToken,
    login, register,
    get, post,
    getProfile, getQuests,
    startQuest, completeQuest,
    getLeaderboard,
  };
})();
