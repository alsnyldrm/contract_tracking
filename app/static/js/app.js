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
  let res;
  try {
    res = await fetch(url, { credentials: 'same-origin', ...options, headers });
  } catch (e) {
    throw new Error('Sunucuya bağlanılamadı. Lütfen ağ bağlantınızı kontrol edin.');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'İstek başarısız' }));
    throw new Error(err.detail || 'İstek başarısız');
  }
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return res.json();
  return res;
}

/* ── Toast notifications ── */
function showToast(message, type = 'info', duration = 4000) {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const icons = { success: '✓', error: '✕', info: 'ℹ', warn: '⚠' };
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${message}</span>`;
  container.appendChild(el);
  setTimeout(() => {
    el.style.transition = 'opacity .3s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 300);
  }, duration);
}

async function saveUIPreference(changes) {
  try {
    await api('/api/profile/preferences', { method: 'PUT', body: JSON.stringify(changes) });
  } catch (e) { /* sessizce geç */ }
}

async function logout() {
  try {
    await api('/auth/logout', { method: 'POST', body: JSON.stringify({}) });
  } catch (e) { /* devam et */ }
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

  const shell       = document.getElementById('appShell');
  const toggleBtn   = document.getElementById('toggleSidebar');
  const closeBtn    = document.getElementById('sidebarCloseBtn');
  const toggleTheme = document.getElementById('toggleTheme');

  function setSidebarCollapsed(collapsed) {
    shell.classList.toggle('sidebar-collapsed', collapsed);
    saveUIPreference({ sidebar_collapsed: collapsed });
  }

  /* Topbar butonu: kapalıysa aç, açıksa kapat */
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      setSidebarCollapsed(!shell.classList.contains('sidebar-collapsed'));
    });
  }

  /* Sidebar içindeki kapat butonu */
  if (closeBtn) {
    closeBtn.addEventListener('click', () => setSidebarCollapsed(true));
  }

  if (toggleTheme) {
    toggleTheme.addEventListener('click', async () => {
      const html = document.documentElement;
      const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-theme', next);
      toggleTheme.textContent = next === 'dark' ? '☀' : '🌙';
      await saveUIPreference({ dark_mode: next === 'dark' });
    });
    const current = document.documentElement.getAttribute('data-theme');
    toggleTheme.textContent = current === 'dark' ? '☀' : '🌙';
  }
});
