// Campaign details page — Phase 2 (live progress + jobs table)
(function () {
  const { api, toast, fmtDate, fmtBytes } = window.IGA;
  const id = window.CAMPAIGN_ID;

  const DIST_LABELS = { same: 'Same → All', one_per_account: 'One File / Account', round_robin: 'Round Robin' };
  const set = (sel, val) => { const el = document.querySelector(sel); if (el) el.textContent = val; };

  async function load() {
    try {
      const [d, jobs] = await Promise.all([
        api(`/v1/campaigns/${id}`),
        api(`/v1/campaigns/${id}/jobs`).catch(() => []),
      ]);
      render(d, jobs);
      return d;
    } catch (err) {
      toast(err.message, 'error');
      return null;
    }
  }

  function render(d, jobs) {
    const status = document.getElementById('d-status');
    status.textContent = d.status;
    status.className = `status-tag is-${d.status}`;
    set('#d-content', d.content_type === 'reel' ? 'Reel' : 'Static Post');
    set('#d-files', String(d.files.length));
    set('#d-accounts', String(d.account_quantity));
    set('#d-dist', DIST_LABELS[d.distribution_mode] || d.distribution_mode);
    set('#d-audio', d.audio_mode === 'ig_music' ? 'Instagram Music' : 'Original Audio');
    if (d.audio_mode === 'ig_music') {
      document.getElementById('d-song-row').classList.remove('hidden');
      set('#d-song', d.music_search || '—');
    }
    set('#d-created', fmtDate(d.created_at));
    set('#d-caption', d.caption || '—');

    // Progress counts
    const c = d.job_counts || {};
    const total = c.total || 0;
    const done = (c.success || 0) + (c.failed || 0) + (c.action_required || 0);
    const pct = total ? Math.round((done / total) * 100) : 0;
    document.getElementById('progress-bar').style.width = `${pct}%`;
    set('#progress-done', String(done));
    set('#progress-total', String(total));
    set('#s-queued', String(c.queued || 0));
    set('#s-running', String(c.running || 0));
    set('#s-success', String(c.success || 0));
    set('#s-failed', String(c.failed || 0));
    set('#s-action-required', String(c.action_required || 0));

    // Files
    const list = document.getElementById('detail-files');
    document.getElementById('file-total').textContent = `${d.files.length} file(s)`;
    list.innerHTML = d.files.map((f) => `
      <li>
        <span class="file-name" title="${escapeHtml(f.filename)}">${escapeHtml(f.filename)}</span>
        <span class="file-size">${fmtBytes(f.size_bytes)} · ${escapeHtml(f.file_type)}</span>
      </li>
    `).join('') || '<li class="empty-cell">No files</li>';

    // Jobs table
    const tbody = document.getElementById('jobs-tbody');
    document.getElementById('jobs-count').textContent = `${jobs.length} job(s)`;
    if (!jobs.length) {
      tbody.innerHTML = `<tr><td colspan="8" class="empty-cell">No jobs yet — click Start Posting on the dashboard to create them.</td></tr>`;
      return;
    }
    tbody.innerHTML = jobs.map((j) => `
      <tr data-testid="job-row-${j.id}">
        <td><span class="mono">#${j.id}</span></td>
        <td>#${j.account_id ?? '—'}</td>
        <td>#${j.file_id ?? '—'}</td>
        <td><span class="status-tag is-${j.status}">${j.status.toUpperCase().replace('_', ' ')}</span></td>
        <td>${j.attempt_count}</td>
        <td>${j.started_at ? fmtDate(j.started_at) : '—'}</td>
        <td>${j.completed_at ? fmtDate(j.completed_at) : '—'}</td>
        <td class="mono log-msg" title="${escapeHtml(j.error_message || '')}">${escapeHtml((j.error_message || '').slice(0, 120))}</td>
      </tr>
    `).join('');
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  document.querySelectorAll('[data-action]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const action = btn.dataset.action;
      try {
        await api(`/v1/campaigns/${id}/${action}`, { method: 'POST' });
        toast(`Campaign ${action}`, 'success');
        load();
      } catch (err) {
        toast(err.message || 'Action failed', 'error');
      }
    });
  });

  // Poll: fast (2s) while any job is queued/running, slow (10s) otherwise
  let pollTimer = null;
  async function tick() {
    const d = await load();
    const c = (d && d.job_counts) || {};
    const active = (c.queued || 0) + (c.running || 0);
    const delay = active > 0 ? 2000 : 10000;
    pollTimer = setTimeout(tick, delay);
  }
  tick();
  window.addEventListener('beforeunload', () => clearTimeout(pollTimer));
})();
