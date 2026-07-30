// Campaigns list page
(function () {
  const { api, toast, fmtDate } = window.IGA;
  const tbody = document.getElementById('campaigns-tbody');
  let all = [];
  let filter = 'all';

  document.querySelectorAll('.filter-cluster .chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.filter-cluster .chip').forEach((c) => c.classList.remove('chip--active'));
      chip.classList.add('chip--active');
      filter = chip.dataset.filter;
      render();
    });
  });

  async function load() {
    try {
      all = await api('/v1/campaigns');
      render();
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="10" class="empty-cell">${err.message}</td></tr>`;
    }
  }

  async function render() {
    const rows = filter === 'all' ? all : all.filter((c) => c.status === filter);
    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="10" class="empty-cell">No campaigns${filter !== 'all' ? ` with status "${filter}"` : ' yet — create one from the Dashboard'}.</td></tr>`;
      return;
    }
    // Fetch counts per campaign (small N in Phase 1)
    const details = await Promise.all(rows.map((c) =>
      api(`/v1/campaigns/${c.id}`).catch(() => null)
    ));
    tbody.innerHTML = details.map((d) => {
      if (!d) return '';
      const counts = d.job_counts || {};
      const total = counts.total || 0;
      const done = (counts.successful || 0) + (counts.failed || 0);
      const pct = total ? Math.round((done / total) * 100) : 0;
      return `
        <tr onclick="location.href='/api/campaigns/${d.id}'" style="cursor:pointer" data-testid="campaign-row-${d.id}">
          <td><span class="mono">#${d.id}</span></td>
          <td>${d.content_type === 'reel' ? 'Reel' : 'Static'}</td>
          <td>${d.files.length}</td>
          <td>${d.account_quantity}</td>
          <td>${distLabel(d.distribution_mode)}</td>
          <td><span class="status-tag is-${d.status}">${d.status}</span></td>
          <td>${total ? `${pct}%` : '—'}</td>
          <td>${counts.successful || 0}</td>
          <td>${counts.failed || 0}</td>
          <td>${fmtDate(d.created_at)}</td>
        </tr>
      `;
    }).join('');
  }

  function distLabel(m) {
    return ({ same: 'Same → All', one_per_account: 'One / Acct', round_robin: 'Round Robin' })[m] || m;
  }

  load();
})();
