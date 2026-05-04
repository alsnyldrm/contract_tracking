let autoTimer = null;

async function loadTypes() {
  const types = await api('/api/logs/types');
  const sel = document.getElementById('logType');
  sel.innerHTML = types.map(t => `<option value='${t}'>${t}</option>`).join('');
}

async function loadLogs() {
  const logType = document.getElementById('logType').value;
  const limit = document.getElementById('logLimit').value;
  const level = document.getElementById('logLevel').value;
  const search = document.getElementById('logSearch').value;
  const data = await api(`/api/logs/view?log_type=${logType}&limit=${limit}&level=${encodeURIComponent(level)}&search=${encodeURIComponent(search)}`);
  const tbody = document.querySelector('#logTable tbody');
  tbody.innerHTML = data.rows.map(r => `<tr><td>${r.timestamp || ''}</td><td>${r.level || ''}</td><td>${r.module || ''}</td><td>${r.message || ''}</td><td><button class='btn' onclick='showLogDetail(${JSON.stringify(JSON.stringify(r))})'>Detay</button></td></tr>`).join('');
}

function showLogDetail(raw) {
  alert(JSON.parse(raw));
}

function downloadLog() {
  const logType = document.getElementById('logType').value;
  window.open(`/api/logs/download?log_type=${logType}`, '_blank');
}

function exportLogCsv() {
  const logType = document.getElementById('logType').value;
  window.open(`/api/logs/export-csv?log_type=${logType}`, '_blank');
}

document.addEventListener('DOMContentLoaded', async () => {
  await loadTypes();
  await loadLogs();
  autoTimer = setInterval(() => loadLogs().catch(() => {}), 5000);
});
