// Shared utilities for IG Automation OS
window.IGA = (function () {
  const API = '/api';

  function toast(msg, type) {
    const root = document.getElementById('toast-root');
    if (!root) { console.log('[toast]', msg); return; }
    const el = document.createElement('div');
    el.className = 'toast' + (type ? ' is-' + type : '');
    el.textContent = msg;
    root.appendChild(el);
    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transition = 'opacity 220ms ease';
      setTimeout(() => el.remove(), 260);
    }, 3800);
  }

  async function api(path, opts) {
    const res = await fetch(API + path, {
      credentials: 'same-origin',
      headers: opts && opts.body && !(opts.body instanceof FormData)
        ? { 'Content-Type': 'application/json', ...(opts.headers || {}) }
        : (opts && opts.headers) || {},
      ...opts,
    });
    let data = null;
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) data = await res.json();
    if (!res.ok) {
      const msg = (data && (data.detail || data.message)) || `HTTP ${res.status}`;
      throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
    return data;
  }

  function fmtBytes(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    let n = bytes;
    while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(n >= 100 ? 0 : 1)} ${units[i]}`;
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      month: 'short', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  }

  function fmtTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleTimeString(undefined, { hour12: false });
  }

  return { API, api, toast, fmtBytes, fmtDate, fmtTime };
})();
