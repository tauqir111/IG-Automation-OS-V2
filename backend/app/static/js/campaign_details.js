// Campaign details page
(function () {
  const { api, toast, fmtDate, fmtBytes } = window.IGA;
  const id = window.CAMPAIGN_ID;

  async function load() {
    try {
      const d = await api(`/v1/campaigns/${id}`);
      render(d);
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  function render(d) {
    const set = (sel, val) => { const el = document.querySelector(sel); if (el) el.textContent = val; };
    const status = document.getElementById('d-status');
    status.textContent = d.status;
    status.className = `status-tag is-${d.status}`;
    set('#d-content', d.content_type === 'reel' ? 'Reel' : 'Static Post');
    set('#d-files', String(d.files.length));
    set('#d-accounts', String(d.account_quantity));
    set('#d-dist', ({ same: 'Same → All', one_per_account: 'One File / Account', round_robin: 'Round Robin' })[d.distribution_mode]);
    set('#d-audio', d.audio_mode === 'ig_music' ? 'Instagram Music' : 'Original Audio');
    if (d.audio_mode === 'ig_music') {
      document.getElementById('d-song-row').classList.remove('hidden');
      set('#d-song', d.music_search || '—');
    }
    set('#d-created', fmtDate(d.created_at));
    set('#d-caption', d.caption || '—');

    // Progress
    const c = d.job_counts || {};
    const total = c.total || 0;
    const done = (c.successful || 0) + (c.failed || 0);
    const pct = total ? Math.round((done / total) * 100) : 0;
    document.getElementById('progress-bar').style.width = `${pct}%`;
    set('#progress-done', String(done));
    set('#progress-total', String(total));
    set('#s-queued', String(c.queued || 0));
    set('#s-processing', String(c.processing || 0));
    set('#s-successful', String(c.successful || 0));
    set('#s-failed', String(c.failed || 0));

    // Files
    const list = document.getElementById('detail-files');
    document.getElementById('file-total').textContent = `${d.files.length} file(s)`;
    list.innerHTML = d.files.map((f) => `
      <li>
        <span class="file-name" title="${escapeHtml(f.filename)}">${escapeHtml(f.filename)}</span>
        <span class="file-size">${fmtBytes(f.size_bytes)} · ${escapeHtml(f.file_type)}</span>
      </li>
    `).join('') || '<li class="empty-cell">No files</li>';
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

  load();
})();
