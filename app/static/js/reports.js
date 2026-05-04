let reportModules = [];
let currentRows = [];

async function loadModules() {
  reportModules = await api('/api/reports/modules');
  const tbody = document.querySelector('#reportModuleTable tbody');
  const select = document.getElementById('reportCode');
  select.innerHTML = '';
  tbody.innerHTML = reportModules.map(m => {
    if (m.is_active) {
      const opt = document.createElement('option');
      opt.value = m.code;
      opt.textContent = m.name;
      select.appendChild(opt);
    }
    return `<tr><td>${m.name}</td><td>${m.is_active ? 'Aktif' : 'Pasif'}</td><td>${window.CT_APP.role === 'admin' ? `<button class='btn' onclick='toggleModule(${m.id}, ${!m.is_active})'>${m.is_active ? 'Pasifleştir' : 'Aktifleştir'}</button>` : '-'}</td></tr>`;
  }).join('');
}

async function toggleModule(id, isActive) {
  await api('/api/reports/modules/' + id, { method: 'PUT', body: JSON.stringify({ is_active: isActive }) });
  loadModules();
}

async function runReport() {
  const code = document.getElementById('reportCode').value;
  const data = await api('/api/reports/' + code);
  currentRows = data.rows;
  const thead = document.querySelector('#reportTable thead');
  const tbody = document.querySelector('#reportTable tbody');
  if (!currentRows.length) {
    thead.innerHTML = '<tr><th>Sonuç yok</th></tr>';
    tbody.innerHTML = '';
    return;
  }
  const cols = Object.keys(currentRows[0]);
  thead.innerHTML = '<tr>' + cols.map(c => `<th>${c}</th>`).join('') + '</tr>';
  tbody.innerHTML = currentRows.map(r => '<tr>' + cols.map(c => `<td>${r[c] ?? ''}</td>`).join('') + '</tr>').join('');
}

function exportReport(fmt) {
  const code = document.getElementById('reportCode').value;
  window.open(`/api/reports/${code}/export/${fmt}`, '_blank');
}

document.addEventListener('DOMContentLoaded', () => loadModules().catch(e => alert(e.message)));
