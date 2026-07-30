// Logs page
(function () {
  const { api, toast, fmtTime } = window.IGA;
  const list = document.getElementById('log-list');
  let level = '';

  document.querySelectorAll('.filter-cluster .chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.filter-cluster .chip').forEach((c) => c.classList.remove('chip--active'));
      chip.classList.add('chip--active');
      level = chip.dataset.level || '';
      load();
    });
  });
  document.getElementById('refresh-logs').addEventListener('click', () => load());

  async function load() {
    try {
      const rows = await api(`/v1/logs${level ? `?level=${encodeURIComponent(level)}` : ''}`);
      if (!rows.length) { list.innerHTML = '<div class="log-empty">No log entries.</div>'; return; }
      list.innerHTML = rows.map((r) => `
        <div class="log-row" data-testid="log-row-${r.id}">
          <span class="log-time">${fmtTime(r.created_at)}</span>
          <span class="log-level ${r.level}">${r.level}</span>
          <span class="log-msg">${escapeHtml(r.message)}</span>
        </div>
      `).join('');
    } catch (err) {
      list.innerHTML = `<div class="log-empty">${err.message}</div>`;
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  load();
  const timer = setInterval(load, 15000);
  window.addEventListener('beforeunload', () => clearInterval(timer));
})();
