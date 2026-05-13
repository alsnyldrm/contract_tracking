/* ── CSRF ── */
function getCsrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
}

/* ── API helper ── */
async function api(url, options = {}) {
  const headers = { ...(options.headers || {}) };
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

/* ── Toast ── */
function showToast(message, type = 'info', duration = 4500) {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const icons = { success: '✓', error: '✕', info: 'ℹ', warn: '⚠' };
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `<span class="toast-icon">${icons[type] || 'ℹ'}</span><span>${message}</span>`;
  container.appendChild(el);
  setTimeout(() => {
    el.style.transition = 'opacity .3s, transform .3s';
    el.style.opacity = '0';
    el.style.transform = 'translateX(50px)';
    setTimeout(() => el.remove(), 300);
  }, duration);
}

/* ── Confirm dialog ── */
function showConfirm(message, title = 'Onay Gerekli') {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';
    overlay.innerHTML = `
      <div class="confirm-box">
        <h4>${title}</h4>
        <p>${message}</p>
        <div class="confirm-actions">
          <button class="btn" id="confirmNo">Hayır, İptal</button>
          <button class="btn btn-danger" id="confirmYes">Evet, Devam Et</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#confirmYes').onclick = () => { overlay.remove(); resolve(true); };
    overlay.querySelector('#confirmNo').onclick  = () => { overlay.remove(); resolve(false); };
    overlay.addEventListener('click', e => { if (e.target === overlay) { overlay.remove(); resolve(false); } });
  });
}

/* ── UI Preference persistence ── */
async function saveUIPreference(changes) {
  try {
    await api('/api/profile/preferences', { method: 'PUT', body: JSON.stringify(changes) });
  } catch { /* sessizce geç */ }
}

/* ── Logout ── */
async function logout() {
  try { await api('/auth/logout', { method: 'POST', body: JSON.stringify({}) }); } catch { /* devam */ }
  location.href = '/login';
}

/* ── Clock ── */
function tickClock() {
  const box = document.getElementById('clock');
  if (!box) return;
  const now = new Date();
  box.textContent = now.toLocaleString('tr-TR', { timeZone: window.CT_APP?.timezone || 'Europe/Istanbul', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/* ── Notifications ── */
async function loadNotifications() {
  try {
    const data = await api('/api/dashboard/notifications');
    const badge = document.getElementById('notifBadge');
    const list  = document.getElementById('notifList');
    const unread = data.filter(n => !n.is_read).length;
    if (badge) { badge.textContent = unread; badge.style.display = unread > 0 ? '' : 'none'; }
    if (list) {
      if (data.length === 0) {
        list.innerHTML = '<div class="empty-state" style="padding:24px"><div class="empty-icon">🔔</div><p>Bildirim yok</p></div>';
      } else {
        list.innerHTML = data.map(n => `
          <div class="doc-item" style="padding:10px 2px;${!n.is_read ? 'background:var(--primary-light);border-radius:6px;padding:10px 8px;' : ''}">
            <div class="doc-info">
              <div class="doc-name">${escHtml(n.title)}</div>
              <div class="doc-meta">${escHtml(n.message)}</div>
            </div>
          </div>`).join('');
      }
    }
  } catch { /* sessizce geç */ }
}

function closeNotifModal() {
  document.getElementById('notifModal')?.classList.remove('open');
}

/* ── Sidebar ── */
function setSidebarCollapsed(collapsed) {
  const shell = document.getElementById('appShell');
  if (!shell) return;
  shell.classList.toggle('sidebar-collapsed', collapsed);
  saveUIPreference({ sidebar_collapsed: collapsed });
}

/* ── Badges / status helpers ── */
function statusBadge(status) {
  const map = {
    'Taslak':       'badge-gray',
    'Aktif':        'badge-green',
    'Yaklaşıyor':   'badge-yellow',
    'Süresi Doldu': 'badge-red',
    'İptal':        'badge-gray',
    'Yenilendi':    'badge-blue',
  };
  return `<span class="badge ${map[status] || 'badge-gray'}">${escHtml(status)}</span>`;
}

function criticalBadge(level) {
  const map = {
    'Düşük':  'badge-green',
    'Orta':   'badge-yellow',
    'Yüksek': 'badge-orange',
    'Kritik': 'badge-red',
  };
  return `<span class="badge ${map[level] || 'badge-gray'}">${escHtml(level)}</span>`;
}

function escHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatDate(dateStr) {
  if (!dateStr || dateStr === 'None') return '—';
  try {
    const raw = String(dateStr).trim();
    const isoMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T\s].*)?$/);
    if (isoMatch) return `${isoMatch[3]}.${isoMatch[2]}.${isoMatch[1]}`;
    const trMatch = raw.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    if (trMatch) return raw;

    const d = new Date(raw);
    if (isNaN(d.getTime())) return raw;
    return d.toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch { return dateStr; }
}

function formatCurrency(amount, symbol) {
  if (!amount) return '—';
  return Number(amount).toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + (symbol ? ' ' + symbol : '');
}

/* ── Chart.js dark mode helper ── */
function getChartTheme() {
  const dark = document.documentElement.getAttribute('data-theme') === 'dark';
  return {
    gridColor: dark ? 'rgba(255,255,255,.08)' : 'rgba(0,0,0,.07)',
    textColor: dark ? '#8fa8c4' : '#667085',
    tooltipBg: dark ? '#1a2d45' : '#fff',
    tooltipColor: dark ? '#e2eaf5' : '#1d2939',
  };
}

function applyChartDefaults() {
  const t = getChartTheme();
  Chart.defaults.color = t.textColor;
  Chart.defaults.borderColor = t.gridColor;
}

/* ── DOMContentLoaded ── */
document.addEventListener('DOMContentLoaded', () => {
  tickClock();
  setInterval(tickClock, 1000);
  applyChartDefaults();

  const shell     = document.getElementById('appShell');
  const closeBtn  = document.getElementById('sidebarCloseBtn');
  const themeBtn  = document.getElementById('toggleTheme');
  const notifBtn  = document.getElementById('notifBtn');

  if (closeBtn) {
    closeBtn.addEventListener('click', () => setSidebarCollapsed(!shell?.classList.contains('sidebar-collapsed')));
  }

  if (themeBtn) {
    const current = document.documentElement.getAttribute('data-theme');
    themeBtn.textContent = current === 'dark' ? '☀' : '🌙';
    themeBtn.addEventListener('click', async () => {
      const html = document.documentElement;
      const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-theme', next);
      themeBtn.textContent = next === 'dark' ? '☀' : '🌙';
      applyChartDefaults();
      await saveUIPreference({ dark_mode: next === 'dark' });
    });
  }

  if (notifBtn) {
    notifBtn.addEventListener('click', () => {
      const modal = document.getElementById('notifModal');
      modal?.classList.toggle('open');
      if (modal?.classList.contains('open')) loadNotifications();
    });
  }

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal.open').forEach(m => m.classList.remove('open'));
      document.querySelectorAll('.confirm-overlay').forEach(m => m.remove());
    }
  });

  loadNotifications();
  setInterval(loadNotifications, 60000);
});
