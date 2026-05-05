let autoTimer = null;
const LEVEL_BADGE = {
  DEBUG:    '<span class="badge badge-gray">DEBUG</span>',
  INFO:     '<span class="badge badge-blue">INFO</span>',
  WARNING:  '<span class="badge badge-yellow">WARNING</span>',
  ERROR:    '<span class="badge badge-red">ERROR</span>',
  CRITICAL: '<span class="badge badge-red" style="font-weight:800">CRITICAL</span>',
};

async function loadTypes() {
  try {
    const types = await api('/api/logs/types');
    const sel = document.getElementById('logType');
    sel.innerHTML = types.map(t => `<option value="${escHtml(t)}">${escHtml(t)}</option>`).join('');
  } catch { /* sessiz */ }
}

async function loadLogs() {
  const logType  = document.getElementById('logType').value;
  const limit    = document.getElementById('logLimit').value;
  const level    = document.getElementById('logLevel').value;
  const search   = document.getElementById('logSearch').value;
  const statusEl = document.getElementById('logStatus');
  const tbody    = document.getElementById('logTbody');

  statusEl.textContent = 'Yükleniyor…';

  try {
    const data = await api(
      `/api/logs/view?log_type=${encodeURIComponent(logType)}&limit=${limit}&level=${encodeURIComponent(level)}&search=${encodeURIComponent(search)}`
    );

    const rows = data.rows || [];
    statusEl.textContent = `${rows.length} kayıt gösteriliyor (son güncelleme: ${new Date().toLocaleTimeString('tr-TR')})`;

    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state" style="padding:24px"><div class="empty-icon">📋</div><p style="font-weight:600">Log kaydı bulunamadı</p></div></td></tr>`;
      return;
    }

    tbody.innerHTML = rows.map(r => {
      const lvl    = (r.level || '').toUpperCase();
      const rowCls = `log-row-${lvl}`;
      const badge  = LEVEL_BADGE[lvl] || `<span class="badge badge-gray">${escHtml(r.level || '?')}</span>`;
      return `<tr class="${rowCls}">
        <td class="td-nowrap" style="font-size:11.5px;font-family:monospace">${escHtml(r.timestamp || '')}</td>
        <td>${badge}</td>
        <td class="td-muted" style="font-size:12px">${escHtml(r.module || r.name || '')}</td>
        <td style="font-size:12.5px">${escHtml(r.message || '')}</td>
        <td><button class="btn btn-xs" onclick='showLogDetail(${JSON.stringify(JSON.stringify(r))})'>Detay</button></td>
      </tr>`;
    }).join('');
  } catch (e) {
    statusEl.textContent = 'Hata: ' + e.message;
    tbody.innerHTML = `<tr><td colspan="5" class="td-muted" style="text-align:center;padding:24px">${escHtml(e.message)}</td></tr>`;
  }
}

function showLogDetail(raw) {
  let row;
  try { row = JSON.parse(raw); } catch { row = { raw }; }
  const el = document.getElementById('logDetailContent');
  if (el) {
    el.textContent = JSON.stringify(row, null, 2);
    document.getElementById('logDetailModal')?.classList.add('open');
  }
}

function downloadLog() {
  const logType = document.getElementById('logType').value;
  window.open(`/api/logs/download?log_type=${encodeURIComponent(logType)}`, '_blank');
}

function exportLogCsv() {
  const logType = document.getElementById('logType').value;
  window.open(`/api/logs/export-csv?log_type=${encodeURIComponent(logType)}`, '_blank');
}

function toggleAutoRefresh() {
  const checked = document.getElementById('autoRefresh').checked;
  if (checked) {
    autoTimer = setInterval(() => loadLogs().catch(() => {}), 5000);
  } else {
    clearInterval(autoTimer);
    autoTimer = null;
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  await loadTypes();
  await loadLogs();
});
