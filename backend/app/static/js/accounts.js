// Accounts page — Phase 2 session onboarding
(function () {
  const { api, toast, fmtDate } = window.IGA;
  const tbody = document.getElementById('accounts-tbody');
  const banner = document.getElementById('env-banner');

  const SESSION_LABEL = {
    connected: 'CONNECTED',
    login_required: 'LOGIN REQUIRED',
    expired: 'EXPIRED',
    connecting: 'CONNECTING…',
    verifying: 'VERIFYING…',
    busy: 'BUSY',
    unknown: 'UNKNOWN',
  };

  function deriveStatus(a) {
    if (a.account_status === 'disabled') return { key: 'disabled', label: 'DISABLED' };
    if (a.session_status === 'busy') return { key: 'busy', label: 'BUSY' };
    if (a.session_status === 'connecting') return { key: 'connecting', label: 'CONNECTING' };
    if (a.session_status === 'verifying') return { key: 'verifying', label: 'VERIFYING' };
    if (a.session_status === 'connected') return { key: 'available', label: 'AVAILABLE' };
    return { key: 'unavailable', label: 'UNAVAILABLE' };
  }

  async function loadEnvironment() {
    try {
      const env = await api('/v1/accounts/environment');
      banner.classList.remove('hidden', 'is-warn', 'is-error', 'is-ok');
      banner.classList.add(`is-${env.level}`);
      banner.innerHTML = `
        <span class="env-icon">${env.level === 'ok' ? '●' : '⚠'}</span>
        <div>
          <div class="env-title">${env.level === 'ok' ? 'Browser worker ready' : 'Session onboarding notice'}</div>
          <div class="env-msg">${env.message}</div>
        </div>
      `;
    } catch {}
  }

  async function loadStats() {
    const s = await api('/v1/accounts/stats');
    document.getElementById('stat-total').textContent = s.total;
    document.getElementById('stat-available').textContent = s.available;
    document.getElementById('stat-busy').textContent = s.busy;
    document.getElementById('stat-expired').textContent = s.expired;
    document.getElementById('stat-disabled').textContent = s.disabled;
  }

  let inflightAny = false;

  async function loadList() {
    try {
      const rows = await api('/v1/accounts');
      inflightAny = rows.some((a) => ['connecting', 'verifying'].includes(a.session_status));
      if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="empty-cell">No accounts yet. Add one to allocate a persistent browser profile.</td></tr>`;
        return;
      }
      tbody.innerHTML = rows.map((a) => renderRow(a)).join('');
      wireActions();
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty-cell">${err.message}</td></tr>`;
    }
  }

  function renderRow(a) {
    const st = deriveStatus(a);
    const isBusy = ['connecting', 'verifying'].includes(a.session_status);
    const connected = a.session_status === 'connected';
    const sessionLabel = SESSION_LABEL[a.session_status] || a.session_status.toUpperCase();
    return `
      <tr data-testid="account-row-${a.id}">
        <td><span class="mono">#${a.id}</span></td>
        <td>
          <strong>${escapeHtml(a.account_name)}</strong>
          <div class="row-sub mono">${escapeHtml(shortenPath(a.profile_path))}${a.last_used_at ? ' · last used ' + fmtDate(a.last_used_at) : ''}</div>
        </td>
        <td><span class="status-tag is-${a.session_status}">${sessionLabel}</span></td>
        <td><span class="status-tag is-${st.key}">${st.label}</span></td>
        <td class="cell-actions">
          <button class="btn-primary btn-sm" data-connect="${a.id}" data-testid="connect-${a.id}" ${isBusy ? 'disabled' : ''}>
            ${connected ? 'Open Session' : 'Connect Instagram'}
          </button>
          <button class="btn-ghost btn-sm" data-verify="${a.id}" data-testid="verify-${a.id}" ${isBusy ? 'disabled' : ''}>Verify</button>
          ${a.account_status === 'enabled'
            ? `<button class="btn-ghost btn-sm" data-disable="${a.id}" data-testid="disable-${a.id}">Disable</button>`
            : `<button class="btn-ghost btn-sm" data-enable="${a.id}" data-testid="enable-${a.id}">Enable</button>`}
          <button class="btn-ghost btn-sm" data-delete="${a.id}" data-testid="delete-${a.id}" ${isBusy ? 'disabled' : ''}>Delete</button>
        </td>
      </tr>
    `;
  }

  function shortenPath(p) {
    if (!p) return '';
    const parts = p.split('/');
    return '…/' + parts.slice(-2).join('/');
  }

  function wireActions() {
    tbody.querySelectorAll('[data-connect]').forEach((b) => b.addEventListener('click', async () => {
      try {
        const r = await api(`/v1/accounts/${b.dataset.connect}/connect`, { method: 'POST' });
        toast(r.message || 'Connect started', 'info');
        refresh();
      } catch (err) {
        toast(err.message, 'error');
      }
    }));
    tbody.querySelectorAll('[data-verify]').forEach((b) => b.addEventListener('click', async () => {
      try {
        const r = await api(`/v1/accounts/${b.dataset.verify}/verify`, { method: 'POST' });
        toast(r.message || 'Verification started', 'info');
        refresh();
      } catch (err) {
        toast(err.message, 'error');
      }
    }));
    tbody.querySelectorAll('[data-disable]').forEach((b) => b.addEventListener('click', async () => {
      try {
        await api(`/v1/accounts/${b.dataset.disable}`, { method: 'PATCH', body: JSON.stringify({ account_status: 'disabled' }) });
        toast('Account disabled', 'warn'); refresh();
      } catch (err) { toast(err.message, 'error'); }
    }));
    tbody.querySelectorAll('[data-enable]').forEach((b) => b.addEventListener('click', async () => {
      try {
        await api(`/v1/accounts/${b.dataset.enable}`, { method: 'PATCH', body: JSON.stringify({ account_status: 'enabled' }) });
        toast('Account enabled', 'success'); refresh();
      } catch (err) { toast(err.message, 'error'); }
    }));
    tbody.querySelectorAll('[data-delete]').forEach((b) => b.addEventListener('click', async () => {
      if (!confirm('Delete this account? The persistent browser profile directory will remain on disk.')) return;
      try {
        await api(`/v1/accounts/${b.dataset.delete}`, { method: 'DELETE' });
        toast('Account deleted', 'warn'); refresh();
      } catch (err) { toast(err.message, 'error'); }
    }));
  }

  document.getElementById('add-account-btn').addEventListener('click', async () => {
    const name = document.getElementById('new-account-name').value.trim();
    if (!name) { toast('Enter an account name', 'error'); return; }
    try {
      await api('/v1/accounts', { method: 'POST', body: JSON.stringify({ account_name: name }) });
      document.getElementById('new-account-name').value = '';
      toast(`Account "${name}" added`, 'success');
      refresh();
    } catch (err) {
      toast(err.message || 'Failed to add', 'error');
    }
  });

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function refresh() { loadStats(); loadList(); }

  // Poll faster when a session is in progress
  let pollTimer = null;
  function schedulePoll() {
    clearTimeout(pollTimer);
    const delay = inflightAny ? 3000 : 15000;
    pollTimer = setTimeout(async () => { await refresh(); schedulePoll(); }, delay);
  }

  (async function init() {
    await loadEnvironment();
    await refresh();
    schedulePoll();
  })();

  window.addEventListener('beforeunload', () => clearTimeout(pollTimer));
})();
