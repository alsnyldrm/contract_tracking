let charts = {};

const WIDGET_DEFS = [
  { key: 'toplam_kurum',      label: 'Toplam Kurum',              icon: '🏛', color: 'blue'   },
  { key: 'toplam_sozlesme',   label: 'Toplam Sözleşme',           icon: '📄', color: 'blue'   },
  { key: 'aktif_sozlesme',    label: 'Aktif Sözleşme',            icon: '✅', color: 'green'  },
  { key: 'suresi_dolmus',     label: 'Süresi Dolmuş',             icon: '⛔', color: 'red'    },
  { key: 'kritik_sozlesme',   label: 'Kritik Seviye',             icon: '🚨', color: 'red'    },
  { key: 'bitecek_7',         label: '7 Günde Bitiyor',           icon: '⏰', color: 'red'    },
  { key: 'bitecek_30',        label: '30 Günde Bitiyor',          icon: '📅', color: 'yellow' },
  { key: 'bitecek_60',        label: '60 Günde Bitiyor',          icon: '📅', color: 'yellow' },
  { key: 'bitecek_90',        label: '90 Günde Bitiyor',          icon: '📅', color: 'yellow' },
  { key: 'aylik_yenilenecek', label: 'Aylık Yenilenecek',         icon: '🔄', color: 'purple' },
  { key: 'toplam_tutar_tl',   label: 'Toplam Tutar (₺)',          icon: '💰', color: 'green'  },
  { key: 'taslak_sozlesme',   label: 'Taslak Sözleşme',           icon: '📝', color: 'blue'   },
  { key: 'iptal_sozlesme',    label: 'İptal Sözleşme',            icon: '🚫', color: 'red'    },
  { key: 'yenilendi_sozlesme',label: 'Yenilenen Sözleşme',        icon: '♻', color: 'purple' },
  { key: 'bu_ay_eklenen',     label: 'Bu Ay Eklenen',             icon: '📌', color: 'blue'   },
];

const STATUS_COLORS = {
  'Aktif':        '#12b76a',
  'Taslak':       '#98a2b3',
  'Yaklaşıyor':   '#fdb022',
  'Süresi Doldu': '#f04438',
  'İptal':        '#667085',
  'Yenilendi':    '#4fa8ff',
};

function getDashFilters() {
  return {
    q:            document.getElementById('dashSearch')?.value     || '',
    institution:  document.getElementById('dashInstitution')?.value || '',
    status:       document.getElementById('dashStatus')?.value     || '',
    critical:     document.getElementById('dashCritical')?.value   || '',
    expiring:     document.getElementById('dashExpiring')?.value   || '',
  };
}

function clearDashFilters() {
  document.getElementById('dashSearch').value      = '';
  document.getElementById('dashInstitution').value = '';
  document.getElementById('dashStatus').value      = '';
  document.getElementById('dashCritical').value    = '';
  document.getElementById('dashExpiring').value    = '';
  loadDashboard();
}

async function loadInstitutionOptions() {
  try {
    const data = await api('/api/institutions?page_size=500');
    const sel = document.getElementById('dashInstitution');
    if (sel) {
      sel.innerHTML = '<option value="">Tüm Kurumlar</option>' +
        data.items.map(i => `<option value="${i.id}">${escHtml(i.name)}</option>`).join('');
    }
  } catch { /* sessiz */ }
}

async function loadDashboard() {
  const f = getDashFilters();
  const params = new URLSearchParams();
  if (f.q)           params.set('q', f.q);
  if (f.institution) params.set('institution_id', f.institution);
  if (f.status)      params.set('status', f.status);
  if (f.critical)    params.set('critical_level', f.critical);
  if (f.expiring)    params.set('expiring_days', f.expiring);

  const grid = document.getElementById('widgetGrid');
  grid.innerHTML = '<div class="widget" style="grid-column:span 5;text-align:center;padding:24px;color:var(--muted)"><div class="spinner"></div><p style="margin:8px 0 0;font-size:13px">Yükleniyor…</p></div>';

  let data;
  try {
    data = await api('/api/dashboard/summary?' + params.toString());
  } catch (e) {
    grid.innerHTML = `<div class="alert alert-error" style="grid-column:1/-1">${escHtml(e.message)}</div>`;
    return;
  }

  renderWidgets(data.widgets);
  renderNearestTable(data.nearest_contracts);
  renderLatestTable(data.latest_contracts);
  renderStatusChart(data.status_chart);
  renderInstitutionTypeChart(data.institution_type_chart);
  renderResponsibleChart(data.responsible_chart);
}

function renderWidgets(widgets) {
  const grid = document.getElementById('widgetGrid');
  grid.innerHTML = WIDGET_DEFS.map(def => {
    let val = widgets[def.key];
    if (val === undefined) val = 0;
    let display;
    if (def.key === 'toplam_tutar_tl') {
      display = Number(val).toLocaleString('tr-TR', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' ₺';
    } else {
      display = Number(val).toLocaleString('tr-TR');
    }
    return `
      <div class="widget widget-${def.color}">
        <div class="widget-icon">${def.icon}</div>
        <div class="label">${def.label}</div>
        <div class="value">${display}</div>
      </div>`;
  }).join('');
}

function renderNearestTable(rows) {
  const tbody = document.querySelector('#nearestTable tbody');
  if (!tbody) return;
  if (!rows || rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:24px">Yaklaşan sözleşme yok</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td class="td-truncate" style="max-width:180px" title="${escHtml(r.contract_name)}">
        <a href="/contracts" style="color:var(--primary);text-decoration:none;font-weight:500">${escHtml(r.contract_name)}</a>
      </td>
      <td class="td-nowrap">${formatDate(r.end_date)}</td>
      <td>${statusBadge(r.status)}</td>
      <td>${criticalBadge(r.critical_level || 'Düşük')}</td>
    </tr>`).join('');
}

function renderLatestTable(rows) {
  const tbody = document.querySelector('#latestTable tbody');
  if (!tbody) return;
  if (!rows || rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--muted);padding:24px">Henüz sözleşme yok</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td class="td-truncate" style="max-width:200px" title="${escHtml(r.contract_name)}">
        <a href="/contracts" style="color:var(--primary);text-decoration:none;font-weight:500">${escHtml(r.contract_name)}</a>
      </td>
      <td class="td-nowrap td-muted" style="font-size:12px">${formatDate(r.created_at)}</td>
      <td>${statusBadge(r.status)}</td>
    </tr>`).join('');
}

function destroyChart(id) {
  if (charts[id]) { charts[id].destroy(); charts[id] = null; }
}

function renderStatusChart(rows) {
  destroyChart('status');
  const ctx = document.getElementById('statusChart');
  if (!ctx || !rows || rows.length === 0) {
    ctx && (ctx.parentElement.querySelector('.chart-empty')?.remove());
    ctx && ctx.parentElement.insertAdjacentHTML('beforeend', '<p class="td-muted" style="text-align:center;font-size:13px;margin:16px 0">Veri yok</p>');
    return;
  }
  ctx.parentElement.querySelector('p')?.remove();
  const t = getChartTheme();
  charts['status'] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: rows.map(x => x.status),
      datasets: [{
        data: rows.map(x => x.count),
        backgroundColor: rows.map(x => STATUS_COLORS[x.status] || '#98a2b3'),
        borderWidth: 2,
        borderColor: t.tooltipBg,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 12, padding: 14, color: t.textColor } },
        tooltip: { backgroundColor: t.tooltipBg, titleColor: t.tooltipColor, bodyColor: t.tooltipColor },
      },
    },
  });
}

function renderInstitutionTypeChart(rows) {
  destroyChart('insttype');
  const ctx = document.getElementById('institutionTypeChart');
  if (!ctx || !rows || rows.length === 0) {
    ctx && ctx.parentElement.querySelector('p')?.remove();
    ctx && ctx.parentElement.insertAdjacentHTML('beforeend', '<p class="td-muted" style="text-align:center;font-size:13px;margin:16px 0">Veri yok</p>');
    return;
  }
  ctx.parentElement.querySelector('p')?.remove();
  const t = getChartTheme();
  const palette = ['#4fa8ff','#12b76a','#fdb022','#f04438','#9e77ed','#32d583','#fd853a','#2ed3b7'];
  charts['insttype'] = new Chart(ctx, {
    type: 'pie',
    data: {
      labels: rows.map(x => x.name),
      datasets: [{
        data: rows.map(x => x.count),
        backgroundColor: rows.map((_, i) => palette[i % palette.length]),
        borderWidth: 2,
        borderColor: t.tooltipBg,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 12, padding: 14, color: t.textColor } },
        tooltip: { backgroundColor: t.tooltipBg, titleColor: t.tooltipColor, bodyColor: t.tooltipColor },
      },
    },
  });
}

function renderResponsibleChart(rows) {
  destroyChart('responsible');
  const ctx = document.getElementById('responsibleChart');
  if (!ctx || !rows || rows.length === 0) {
    ctx && ctx.parentElement.querySelector('p')?.remove();
    ctx && ctx.parentElement.insertAdjacentHTML('beforeend', '<p class="td-muted" style="text-align:center;font-size:13px;margin:16px 0">Veri yok</p>');
    return;
  }
  ctx.parentElement.querySelector('p')?.remove();
  const top = rows.slice(0, 8);
  const t = getChartTheme();
  charts['responsible'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: top.map(x => x.name.length > 18 ? x.name.substring(0, 18) + '…' : x.name),
      datasets: [{
        label: 'Sözleşme',
        data: top.map(x => x.count),
        backgroundColor: '#4fa8ff',
        borderRadius: 5,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: t.tooltipBg, titleColor: t.tooltipColor, bodyColor: t.tooltipColor },
      },
      scales: {
        x: { beginAtZero: true, ticks: { stepSize: 1, color: t.textColor }, grid: { color: t.gridColor } },
        y: { ticks: { color: t.textColor, font: { size: 11 } }, grid: { display: false } },
      },
    },
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  await loadInstitutionOptions();
  await loadDashboard();
});
