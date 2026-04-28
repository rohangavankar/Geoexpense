// Auth utilities — loaded on every page

const Auth = (() => {
  function getToken() { return localStorage.getItem('access_token'); }
  function getRefreshToken() { return localStorage.getItem('refresh_token'); }
  function getUser() {
    try { return JSON.parse(localStorage.getItem('user') || 'null'); } catch { return null; }
  }

  function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    location.href = '/login';
  }

  async function refreshAccessToken() {
    const rt = getRefreshToken();
    if (!rt) return false;
    try {
      const res = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: rt }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      localStorage.setItem('user', JSON.stringify(data.user));
      return true;
    } catch { return false; }
  }

  // Fetch wrapper that adds auth header and handles 401 with token refresh
  async function apiFetch(url, options = {}) {
    const token = getToken();
    const headers = { ...(options.headers || {}) };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (!(options.body instanceof FormData) && !headers['Content-Type'] && options.body) {
      headers['Content-Type'] = 'application/json';
    }

    let res = await fetch(url, { ...options, headers });

    if (res.status === 401) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${getToken()}`;
        res = await fetch(url, { ...options, headers });
      } else {
        logout();
        return res;
      }
    }

    return res;
  }

  function requireAuth() {
    if (!getToken()) {
      location.href = '/login';
      return false;
    }
    return true;
  }

  return { getToken, getUser, logout, apiFetch, requireAuth };
})();
