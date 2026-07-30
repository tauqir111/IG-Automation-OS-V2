// Settings page
(function () {
  const { api, toast } = window.IGA;
  const form = document.getElementById('settings-form');

  async function load() {
    try {
      const s = await api('/v1/settings');
      Object.entries(s).forEach(([k, v]) => {
        const input = form.querySelector(`[name="${k}"]`);
        if (input) input.value = v;
      });
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {};
    new FormData(form).forEach((v, k) => { data[k] = String(v); });
    try {
      await api('/v1/settings', { method: 'PUT', body: JSON.stringify(data) });
      toast('Settings saved', 'success');
    } catch (err) {
      toast(err.message || 'Save failed', 'error');
    }
  });

  load();
})();
