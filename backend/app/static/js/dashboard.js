// Campaign creation flow — bulk upload, quantity, distribution, summary, submit.
(function () {
  const { api, toast, fmtBytes } = window.IGA;

  // In-memory state
  const state = {
    contentType: 'reel',
    files: [],           // { id, filename, size_bytes, file_type }
    accountQuantity: 0,
    distributionMode: 'same',
    audioMode: 'original',
    musicSearch: '',
    caption: '',
    uploading: false,
  };

  const $ = (sel) => document.querySelector(sel);
  const els = {
    form: $('#campaign-form'),
    dropzone: $('#dropzone'),
    fileInput: $('#file-input'),
    dropzoneHint: $('#dropzone-hint'),
    fileList: $('#file-list'),
    fileCount: $('#file-count'),
    fileCountS: $('#file-count-s'),
    clearAll: $('#clear-all'),
    caption: $('#caption'),
    captionCount: $('#caption-count'),
    audioSection: $('#section-audio'),
    musicWrap: $('#music-search-wrap'),
    musicInput: $('#music_search'),
    qtyInput: $('#account_quantity'),
    startBtn: $('#start-btn'),
    // Summary
    sumContent: $('#sum-content'),
    sumFiles: $('#sum-files'),
    sumAccounts: $('#sum-accounts'),
    sumDist: $('#sum-dist'),
    sumAudio: $('#sum-audio'),
    sumSong: $('#sum-song'),
    sumSongRow: $('#sum-song-row'),
    sumJobs: $('#sum-jobs'),
    // Modal
    modal: $('#confirm-modal'),
    modalSummary: $('#modal-summary'),
    modalCancel: $('#modal-cancel'),
    modalConfirm: $('#modal-confirm'),
  };

  const DIST_LABELS = {
    same: 'Same → All Accounts',
    one_per_account: 'One File Per Account',
    round_robin: 'Round Robin',
  };
  const AUDIO_LABELS = { original: 'Original Audio', ig_music: 'Instagram Music' };
  const HINTS = {
    reel: 'Reel: .mp4 .mov .webm .mkv',
    static: 'Static: .jpg .jpeg .png .webp',
  };

  // ---- Content type ----
  els.form.querySelectorAll('input[name="content_type"]').forEach((input) => {
    input.addEventListener('change', () => {
      state.contentType = input.value;
      els.dropzoneHint.textContent = HINTS[state.contentType];
      els.audioSection.classList.toggle('hidden', state.contentType !== 'reel');
      els.fileInput.accept = state.contentType === 'reel'
        ? 'video/*,.mp4,.mov,.webm,.mkv'
        : 'image/*,.jpg,.jpeg,.png,.webp';
      // If files were uploaded for the other type, clear them (they'd be rejected server-side).
      if (state.files.length) {
        toast('Cleared files — content type changed', 'warn');
        clearAllFiles(true);
      }
      updateSummary();
    });
  });

  // ---- Audio ----
  els.form.querySelectorAll('input[name="audio_mode"]').forEach((input) => {
    input.addEventListener('change', () => {
      state.audioMode = input.value;
      els.musicWrap.classList.toggle('hidden', state.audioMode !== 'ig_music');
      updateSummary();
    });
  });
  els.musicInput.addEventListener('input', (e) => {
    state.musicSearch = e.target.value;
    updateSummary();
  });

  // ---- Caption ----
  els.caption.addEventListener('input', (e) => {
    state.caption = e.target.value;
    els.captionCount.textContent = String(e.target.value.length);
  });

  // ---- Distribution ----
  els.form.querySelectorAll('input[name="distribution_mode"]').forEach((input) => {
    input.addEventListener('change', () => {
      state.distributionMode = input.value;
      updateSummary();
    });
  });

  // ---- Quantity ----
  document.querySelectorAll('.qty-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const q = parseInt(btn.dataset.quantity, 10);
      state.accountQuantity = q;
      els.qtyInput.value = q;
      document.querySelectorAll('.qty-btn').forEach((b) => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      updateSummary();
    });
  });
  els.qtyInput.addEventListener('input', (e) => {
    const v = parseInt(e.target.value, 10);
    state.accountQuantity = isNaN(v) ? 0 : v;
    document.querySelectorAll('.qty-btn').forEach((b) => {
      b.classList.toggle('is-active', parseInt(b.dataset.quantity, 10) === state.accountQuantity);
    });
    updateSummary();
  });

  // ---- File uploads ----
  els.dropzone.addEventListener('click', (e) => {
    if (e.target === els.fileInput) return;
    els.fileInput.click();
  });
  els.fileInput.addEventListener('change', (e) => {
    handleFiles(Array.from(e.target.files || []));
    e.target.value = '';
  });
  ;['dragenter', 'dragover'].forEach((evt) =>
    els.dropzone.addEventListener(evt, (e) => {
      e.preventDefault(); e.stopPropagation();
      els.dropzone.classList.add('is-drag');
    })
  );
  ;['dragleave', 'drop'].forEach((evt) =>
    els.dropzone.addEventListener(evt, (e) => {
      e.preventDefault(); e.stopPropagation();
      els.dropzone.classList.remove('is-drag');
    })
  );
  els.dropzone.addEventListener('drop', (e) => {
    const files = Array.from(e.dataTransfer?.files || []);
    if (files.length) handleFiles(files);
  });

  async function handleFiles(fileList) {
    if (!fileList.length) return;
    if (state.uploading) { toast('Upload in progress…', 'warn'); return; }
    state.uploading = true;
    const fd = new FormData();
    fd.append('content_type', state.contentType);
    fileList.forEach((f) => fd.append('files', f));
    try {
      const rows = await api('/v1/campaigns/upload', { method: 'POST', body: fd });
      rows.forEach((r) => state.files.push(r));
      renderFiles();
      toast(`${rows.length} file${rows.length === 1 ? '' : 's'} added`, 'success');
    } catch (err) {
      toast(err.message || 'Upload failed', 'error');
    } finally {
      state.uploading = false;
    }
  }

  async function removeFile(id) {
    try {
      await api(`/v1/campaigns/upload/${id}`, { method: 'DELETE' });
      state.files = state.files.filter((f) => f.id !== id);
      renderFiles();
    } catch (err) {
      toast(err.message || 'Failed to remove file', 'error');
    }
  }

  async function clearAllFiles(silent) {
    const ids = state.files.map((f) => f.id);
    for (const id of ids) {
      try { await api(`/v1/campaigns/upload/${id}`, { method: 'DELETE' }); } catch {}
    }
    state.files = [];
    renderFiles();
    if (!silent) toast('All files cleared');
  }
  els.clearAll.addEventListener('click', () => clearAllFiles(false));

  function renderFiles() {
    els.fileList.innerHTML = '';
    state.files.forEach((f) => {
      const li = document.createElement('li');
      li.dataset.testid = `file-row-${f.id}`;
      li.innerHTML = `
        <span class="file-name" title="${escapeHtml(f.filename)}">${escapeHtml(f.filename)}</span>
        <span class="file-size">${fmtBytes(f.size_bytes)}</span>
        <button type="button" class="file-remove" data-id="${f.id}" data-testid="remove-file-${f.id}">Remove</button>
      `;
      els.fileList.appendChild(li);
    });
    els.fileList.querySelectorAll('.file-remove').forEach((btn) => {
      btn.addEventListener('click', () => removeFile(parseInt(btn.dataset.id, 10)));
    });
    els.fileCount.textContent = String(state.files.length);
    els.fileCountS.textContent = state.files.length === 1 ? '' : 's';
    updateSummary();
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // ---- Summary + estimated jobs ----
  function estimateJobs() {
    const n = state.files.length;
    const q = state.accountQuantity;
    if (!n || !q) return 0;
    if (state.distributionMode === 'same') return q;
    if (state.distributionMode === 'one_per_account') return Math.min(n, q);
    if (state.distributionMode === 'round_robin') return q;
    return 0;
  }

  function updateSummary() {
    els.sumContent.textContent = state.contentType === 'reel' ? 'Reel' : 'Static Post';
    els.sumFiles.textContent = String(state.files.length);
    els.sumAccounts.textContent = String(state.accountQuantity);
    els.sumDist.textContent = DIST_LABELS[state.distributionMode];
    const audioLabel = state.contentType === 'reel' ? AUDIO_LABELS[state.audioMode] : '—';
    els.sumAudio.textContent = audioLabel;
    const showSong = state.contentType === 'reel' && state.audioMode === 'ig_music';
    els.sumSongRow.classList.toggle('hidden', !showSong);
    els.sumSong.textContent = state.musicSearch.trim() || '—';
    els.sumJobs.textContent = String(estimateJobs());
  }

  updateSummary();

  // ---- Submit ----
  els.form.addEventListener('submit', (e) => {
    e.preventDefault();
    const errs = validate();
    if (errs.length) { toast(errs[0], 'error'); return; }
    openModal();
  });

  function validate() {
    const errs = [];
    if (!['reel', 'static'].includes(state.contentType)) errs.push('Select a content type');
    if (state.files.length === 0) errs.push('Add at least one file');
    if (!state.accountQuantity || state.accountQuantity < 1) errs.push('Set account quantity');
    if (!['same', 'one_per_account', 'round_robin'].includes(state.distributionMode)) errs.push('Select a distribution mode');
    if (state.contentType === 'reel' && state.audioMode === 'ig_music' && !state.musicSearch.trim()) {
      errs.push('Enter a song when Instagram Music is enabled');
    }
    return errs;
  }

  function openModal() {
    els.modalSummary.innerHTML = `
      <div><dt>Content</dt><dd>${els.sumContent.textContent}</dd></div>
      <div><dt>Files</dt><dd>${state.files.length}</dd></div>
      <div><dt>Accounts</dt><dd>${state.accountQuantity}</dd></div>
      <div><dt>Distribution</dt><dd>${DIST_LABELS[state.distributionMode]}</dd></div>
      <div class="summary-highlight"><dt>Est. Jobs</dt><dd>${estimateJobs()}</dd></div>
    `;
    els.modal.classList.remove('hidden');
  }
  function closeModal() { els.modal.classList.add('hidden'); }
  els.modalCancel.addEventListener('click', closeModal);
  els.modal.querySelector('.modal-backdrop').addEventListener('click', closeModal);

  els.modalConfirm.addEventListener('click', async () => {
    els.modalConfirm.disabled = true;
    try {
      const payload = {
        content_type: state.contentType,
        caption: state.caption,
        account_quantity: state.accountQuantity,
        distribution_mode: state.distributionMode,
        audio_mode: state.contentType === 'reel' ? state.audioMode : 'original',
        music_search: state.contentType === 'reel' && state.audioMode === 'ig_music' ? state.musicSearch : '',
        file_ids: state.files.map((f) => f.id),
      };
      const campaign = await api('/v1/campaigns', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      toast(`Campaign #${campaign.id} created`, 'success');
      closeModal();
      setTimeout(() => { window.location.href = `/api/campaigns/${campaign.id}`; }, 500);
    } catch (err) {
      toast(err.message || 'Failed to create campaign', 'error');
    } finally {
      els.modalConfirm.disabled = false;
    }
  });
})();
