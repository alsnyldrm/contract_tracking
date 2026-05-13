let activeReportCode = null;
let currentReportRows = [];
let reportModules = [];

const REPORT_COL_LABELS = {
  contract_number:         'Sözleşme No',
  contract_name:           'Sözleşme Adı',
  institution_name:        'Kurum',
  contract_type_name:      'Tür',
  status:                  'Durum',
  critical_level:          'Kritiklik',
  start_date:              'Başlangıç',
  end_date:                'Bitiş',
  renewal_date:            'Yenileme',
  amount:                  'Tutar',
  currency_code:           'Para Birimi',
  vat_included:            'KDV Dahil',
  payment_period:          'Ödeme Periyodu',
  auto_renewal:            'Oto Yenileme',
  responsible_person_name: 'Sorumlu',
  responsible_department:  'Departman',
  document_count:          'Belge Sayısı',
  days_remaining:          'Kalan Gün',
  created_at:              'Oluşturulma',
  updated_at:              'Güncellenme',
};

const DATE_COLUMN_KEYS = new Set([
  'start_date', 'end_date', 'renewal_date', 'created_at', 'updated_at',
  'Başlangıç', 'Bitiş', 'Yenileme', 'Oluşturulma', 'Güncellenme',
]);

function colLabel(key) {
  return REPORT_COL_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

/* ── Modules ── */
async function loadModules() {
  try {
    reportModules = await api('/api/reports/modules');
    renderModuleList();
    await loadInstOptions();
  } catch (e) {
    document.getElementById('reportModuleList').innerHTML =
      `<div class="alert alert-error">${escHtml(e.message)}</div>`;
  }
}

function renderModuleList() {
  const container = document.getElementById('reportModuleList');
  const active = reportModules.filter(m => m.is_active);
  const inactive = reportModules.filter(m => !m.is_active);

  let html = '';
  if (active.length === 0) {
    html = '<div class="empty-state" style="padding:20px"><div class="empty-icon">📊</div><p>Aktif rapor yok</p></div>';
  } else {
    html += active.map(m => `
      <div class="settings-label-row" style="cursor:pointer;padding:10px 8px;border-radius:8px;transition:background .15s"
           onclick="selectReport('${escHtml(m.code)}', '${escHtml(m.name)}')"
           id="rmod-${escHtml(m.code)}"
           onmouseover="this.style.background='var(--primary-light)'"
           onmouseout="this.style.background=''"
      >
        <div>
          <div style="font-weight:500;font-size:13px">${escHtml(m.name)}</div>
          <div style="font-size:11.5px;color:var(--muted)">${escHtml(m.code)}</div>
        </div>
        <span class="badge badge-green">Aktif</span>
      </div>`).join('');
  }

  if (inactive.length > 0 && window.CT_APP.role === 'admin') {
    html += `<div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;padding:14px 8px 4px">Pasif Modüller</div>`;
    html += inactive.map(m => `
      <div class="settings-label-row" style="padding:8px 8px;opacity:.5">
        <div>
          <div style="font-weight:500;font-size:13px">${escHtml(m.name)}</div>
        </div>
        <span class="badge badge-gray">Pasif</span>
      </div>`).join('');
  }

  container.innerHTML = html;
}

function selectReport(code, name) {
  activeReportCode = code;
  document.getElementById('activeReportName').textContent = '📊 ' + name;

  document.querySelectorAll('[id^="rmod-"]').forEach(el => {
    el.style.background = '';
    el.style.fontWeight = '';
  });
  const sel = document.getElementById('rmod-' + code);
  if (sel) { sel.style.background = 'var(--primary-light)'; }

  document.getElementById('exportBtns').style.display = '';
  document.getElementById('reportPlaceholder').style.display = 'none';
  document.getElementById('reportTableWrap').style.display = 'none';
  document.getElementById('reportMeta').style.display = 'none';
  currentReportRows = [];
}

/* ── Run report ── */
async function runReport() {
  if (!activeReportCode) { showToast('Önce bir rapor seçin', 'warn'); return; }

  const btn = document.getElementById('runReportBtn');
  btn.disabled = true; btn.textContent = '⏳ Yükleniyor…';

  const params = new URLSearchParams();
  const dateFrom = document.getElementById('rFilterDateFrom').value;
  const dateTo   = document.getElementById('rFilterDateTo').value;
  const inst     = document.getElementById('rFilterInstitution').value;
  const status   = document.getElementById('rFilterStatus').value;
  if (dateFrom) params.set('start_date', dateFrom);
  if (dateTo)   params.set('end_date', dateTo);
  if (inst)     params.set('institution_id', inst);
  if (status)   params.set('status', status);

  try {
    const data = await api(`/api/reports/${activeReportCode}?${params.toString()}`);
    currentReportRows = data.rows || [];
    renderReportTable();
    document.getElementById('reportCount').textContent = `Toplam ${currentReportRows.length} kayıt`;
    document.getElementById('reportMeta').style.display = '';
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    btn.disabled = false; btn.textContent = '▶ Çalıştır';
  }
}

function renderReportTable() {
  const wrap  = document.getElementById('reportTableWrap');
  const thead = document.getElementById('reportThead');
  const tbody = document.getElementById('reportTbody');

  if (!currentReportRows || currentReportRows.length === 0) {
    wrap.style.display = 'none';
    document.getElementById('reportPlaceholder').style.display = '';
    document.getElementById('reportPlaceholder').innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📭</div>
        <p style="font-weight:600">Sonuç bulunamadı</p>
        <p>Filtrelerinizi değiştirerek tekrar deneyin</p>
      </div>`;
    return;
  }

  document.getElementById('reportPlaceholder').style.display = 'none';
  wrap.style.display = '';

  const cols = Object.keys(currentReportRows[0]);
  thead.innerHTML = '<tr>' + cols.map(c => `<th>${colLabel(c)}</th>`).join('') + '</tr>';
  tbody.innerHTML = currentReportRows.slice(0, 500).map(row =>
    '<tr>' + cols.map(c => {
      const v = row[c];
      if (v === null || v === undefined) return '<td class="td-muted">—</td>';
      if (typeof v === 'boolean') return `<td>${v ? '✓' : '✗'}</td>`;
      if (c === 'status') return `<td>${statusBadge(String(v))}</td>`;
      if (c === 'critical_level') return `<td>${criticalBadge(String(v))}</td>`;
      if (DATE_COLUMN_KEYS.has(c)) return `<td class="td-nowrap">${escHtml(formatDate(v))}</td>`;
      return `<td>${escHtml(String(v))}</td>`;
    }).join('') + '</tr>'
  ).join('');

  if (currentReportRows.length > 500) {
    tbody.innerHTML += `<tr><td colspan="${cols.length}" style="text-align:center;color:var(--muted);padding:10px;font-size:12px">
      İlk 500 kayıt gösteriliyor. Tümü için dışa aktarma yapın.
    </td></tr>`;
  }
}

/* ── Export ── */
function exportReport(fmt) {
  if (!activeReportCode) { showToast('Önce bir rapor seçin', 'warn'); return; }
  const params = new URLSearchParams();
  const dateFrom = document.getElementById('rFilterDateFrom').value;
  const dateTo   = document.getElementById('rFilterDateTo').value;
  const inst     = document.getElementById('rFilterInstitution').value;
  const status   = document.getElementById('rFilterStatus').value;
  if (dateFrom) params.set('start_date', dateFrom);
  if (dateTo)   params.set('end_date', dateTo);
  if (inst)     params.set('institution_id', inst);
  if (status)   params.set('status', status);
  window.open(`/api/reports/${activeReportCode}/export/${fmt}?${params.toString()}`, '_blank');
}

/* ── Institution options ── */
async function loadInstOptions() {
  try {
    const data = await api('/api/institutions?page_size=500');
    const sel = document.getElementById('rFilterInstitution');
    if (!sel) return;
    sel.innerHTML = '<option value="">Tüm Kurumlar</option>' +
      data.items.map(i => `<option value="${i.id}">${escHtml(i.name)}</option>`).join('');
  } catch { /* sessiz */ }
}

document.addEventListener('DOMContentLoaded', loadModules);
