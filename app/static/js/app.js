function getCsrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
}

async function api(url, options = {}) {
  const headers = options.headers || {};
  if (options.method && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method.toUpperCase())) {
    headers['X-CSRF-Token'] = getCsrfToken();
  }
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }
  const res = await fetch(url, { credentials: 'same-origin', ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'İstek başarısız' }));
    throw new Error(err.detail || 'İstek başarısız');
  }
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return res.json();
  return res;
}

async function saveUIPreference(changes) {
  try {
    await api('/api/profile/preferences', { method: 'PUT', body: JSON.stringify(changes) });
  } catch (e) {}
}

async function logout() {
  await api('/auth/logout', { method: 'POST', body: JSON.stringify({}) });
  location.href = '/login';
}

function tickClock() {
  const box = document.getElementById('clock');
  if (!box) return;
  const now = new Date();
  box.textContent = now.toLocaleString('tr-TR', { timeZone: window.CT_APP?.timezone || 'Europe/Istanbul' });
}

document.addEventListener('DOMContentLoaded', () => {
  tickClock();
  setInterval(tickClock, 1000);

  const shell = document.getElementById('appShell');
  const toggleSidebar = document.getElementById('toggleSidebar');
  const toggleTheme = document.getElementById('toggleTheme');

  if (toggleSidebar) {
    toggleSidebar.addEventListener('click', async () => {
      shell.classList.toggle('sidebar-collapsed');
      await saveUIPreference({ sidebar_collapsed: shell.classList.contains('sidebar-collapsed') });
    });
  }

  if (toggleTheme) {
    toggleTheme.addEventListener('click', async () => {
      const html = document.documentElement;
      const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-theme', next);
      await saveUIPreference({ dark_mode: next === 'dark' });
    });
  }
});
