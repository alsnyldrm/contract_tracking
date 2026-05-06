/* ── State ── */
let contractRows   = [];
let contractEditId = null;
let currentDocContractId = null;
let sortField      = 'updated_at';
let sortDir        = 'desc';
let currentPage    = 1;
const PAGE_SIZE    = 20;
let totalCount     = 0;
let debounceTimer  = null;
let ldapTimer      = null;
const CONTRACT_COLUMN_STORAGE_KEY = 'ct_contract_columns_v1';
const CONTRACT_COLUMNS = [
  { key: 'contract_number', label: 'No', index: 1 },
  { key: 'contract_name', label: 'Sözleşme Adı', index: 2 },
  { key: 'institution', label: 'Kurum', index: 3 },
  { key: 'contract_type', label: 'Tür', index: 4 },
  { key: 'status', label: 'Durum', index: 5 },
  { key: 'critical_level', label: 'Kritik', index: 6 },
  { key: 'end_date', label: 'Bitiş', index: 7 },
  { key: 'amount', label: 'Tutar', index: 8 },
  { key: 'responsible', label: 'Sorumlu', index: 9 },
  { key: 'actions', label: 'İşlemler', index: 10 },
];
let contractColumnVisibility = {};

/* ── Debounce ── */
function debounceLoad() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(loadContracts, 400);
}

/* ── Sort ── */
function sortBy(field) {
  if (sortField === field) {
    sortDir = sortDir === 'asc' ? 'desc' : 'asc';
  } else {
    sortField = field;
    sortDir = 'desc';
  }
  currentPage = 1;
  loadContracts();
  updateSortHeaders();
}

function updateSortHeaders() {
  document.querySelectorAll('#contractTable th.sortable').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
  });
  const active = document.querySelector(`#contractTable th[onclick="sortBy('${sortField}')"]`);
  if (active) active.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
}

/* ── Filters ── */
function resetFilters() {
  document.getElementById('search').value          = '';
  document.getElementById('institutionFilter').value = '';
  document.getElementById('typeFilter').value       = '';
  document.getElementById('statusFilter').value     = '';
  document.getElementById('criticalFilter').value   = '';
  document.getElementById('expiringFilter').value   = '';
  currentPage = 1;
  loadContracts();
}

/* ── Column visibility ── */
function getDefaultContractColumnVisibility() {
  const visibility = {};
  CONTRACT_COLUMNS.forEach(col => { visibility[col.key] = true; });
  return visibility;
}

function loadContractColumnVisibility() {
  const visibility = getDefaultContractColumnVisibility();
  try {
    const raw = localStorage.getItem(CONTRACT_COLUMN_STORAGE_KEY);
    if (!raw) return visibility;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return visibility;
    CONTRACT_COLUMNS.forEach(col => {
      if (Object.prototype.hasOwnProperty.call(parsed, col.key)) {
        visibility[col.key] = !!parsed[col.key];
      }
    });
  } catch {
    return visibility;
  }
  return visibility;
}

function saveContractColumnVisibility() {
  try {
    localStorage.setItem(CONTRACT_COLUMN_STORAGE_KEY, JSON.stringify(contractColumnVisibility));
  } catch {
    /* ignore */
  }
}

function applyContractColumnVisibility() {
  const table = document.getElementById('contractTable');
  if (!table) return;

  CONTRACT_COLUMNS.forEach(col => {
    const visible = contractColumnVisibility[col.key] !== false;
    table.querySelectorAll(`thead th:nth-child(${col.index}), tbody td:nth-child(${col.index})`).forEach(cell => {
      cell.style.display = visible ? '' : 'none';
    });
  });
}

function renderContractColumnOptions() {
  const container = document.getElementById('contractColumnOptions');
  if (!container) return;
  container.innerHTML = CONTRACT_COLUMNS.map(col => `
    <label class="column-picker-item">
      <input type="checkbox" data-column-key="${escHtml(col.key)}" ${contractColumnVisibility[col.key] !== false ? 'checked' : ''} />
      <span>${escHtml(col.label)}</span>
    </label>`).join('');

  container.querySelectorAll('input[data-column-key]').forEach(el => {
    el.addEventListener('change', e => {
      const key = e.target.dataset.columnKey;
      contractColumnVisibility[key] = !!e.target.checked;
      saveContractColumnVisibility();
      applyContractColumnVisibility();
    });
  });
}

function setAllContractColumns(visible) {
  CONTRACT_COLUMNS.forEach(col => {
    contractColumnVisibility[col.key] = !!visible;
  });
  saveContractColumnVisibility();
  renderContractColumnOptions();
  applyContractColumnVisibility();
}

function toggleContractColumnMenu(e) {
  if (e) e.stopPropagation();
  const menu = document.getElementById('contractColumnMenu');
  if (!menu) return;
  const isOpen = menu.style.display !== 'none';
  menu.style.display = isOpen ? 'none' : '';
}

function closeContractColumnMenu() {
  const menu = document.getElementById('contractColumnMenu');
  if (menu) menu.style.display = 'none';
}

function initContractColumnChooser() {
  contractColumnVisibility = loadContractColumnVisibility();
  renderContractColumnOptions();
  applyContractColumnVisibility();
}

/* ── Load data ── */
async function loadContracts() {
  const params = new URLSearchParams({
    q:            document.getElementById('search').value || '',
    institution_id: document.getElementById('institutionFilter').value || '',
    contract_type_id: document.getElementById('typeFilter').value || '',
    status:       document.getElementById('statusFilter').value || '',
    critical_level: document.getElementById('criticalFilter').value || '',
    expiring_days: document.getElementById('expiringFilter').value || '',
    sort_by:      sortField,
    sort_dir:     sortDir,
    page:         currentPage,
    page_size:    PAGE_SIZE,
  });

  const tbody = document.getElementById('contractTbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="10"><div class="spinner"></div></td></tr>';
  applyContractColumnVisibility();

  let data;
  try {
    data = await api('/api/contracts?' + params.toString());
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="10" class="td-muted" style="text-align:center;padding:24px">${escHtml(e.message)}</td></tr>`;
    applyContractColumnVisibility();
    return;
  }

  contractRows = data.items;
  totalCount   = data.total;

  if (contractRows.length === 0) {
    tbody.innerHTML = `
      <tr><td colspan="10">
        <div class="empty-state">
          <div class="empty-icon">📄</div>
          <p style="font-weight:600">Sözleşme bulunamadı</p>
          <p>Filtrelerinizi değiştirmeyi deneyin</p>
        </div>
      </td></tr>`;
    applyContractColumnVisibility();
    renderPagination();
    return;
  }

  const isAdmin = window.CT_APP.role === 'admin';
  tbody.innerHTML = contractRows.map(c => {
    const tags = (c.tags || []).map(t => `<span class="tag-chip">${escHtml(t)}</span>`).join('');
    return `<tr>
      <td class="td-nowrap" style="font-weight:600;color:var(--primary)">${escHtml(c.contract_number)}</td>
      <td>
        <div style="font-weight:500">${escHtml(c.contract_name)}</div>
        ${tags ? `<div class="tags-container" style="margin-top:4px">${tags}</div>` : ''}
      </td>
      <td class="td-truncate" style="max-width:150px" title="${escHtml(c.institution_name || '')}">${escHtml(c.institution_name || '—')}</td>
      <td class="td-muted" style="font-size:12px">${escHtml(c.contract_type_name || '—')}</td>
      <td>${statusBadge(c.status)}</td>
      <td>${criticalBadge(c.critical_level)}</td>
      <td class="td-nowrap ${isExpiring(c.end_date) ? 'text-warning' : ''}" style="font-size:12.5px">${formatDate(c.end_date)}</td>
      <td class="td-nowrap" style="font-size:12.5px;text-align:right">${c.amount ? escHtml(Number(c.amount).toLocaleString('tr-TR')) + ' ' + escHtml(c.currency_symbol || '') : '—'}</td>
      <td class="td-truncate" style="max-width:130px;font-size:12.5px" title="${escHtml(c.responsible_person_name || '')}">${escHtml(c.responsible_person_name || '—')}</td>
      <td>
        <div class="table-actions">
          <button class="btn btn-sm" onclick="openDocModal(${c.id}, '${escHtml(c.contract_name).replace(/'/g, "\\'")}')">📎</button>
          ${isAdmin ? `
          <button class="btn btn-sm btn-secondary" onclick="openContractModal(${c.id})">✏</button>
          <button class="btn btn-sm btn-danger" onclick="deleteContract(${c.id})">🗑</button>` : ''}
        </div>
      </td>
    </tr>`;
  }).join('');

  renderPagination();
  applyContractColumnVisibility();
}

function isExpiring(dateStr) {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  const diff = (d - new Date()) / (1000 * 60 * 60 * 24);
  return diff >= 0 && diff <= 30;
}

/* ── Pagination ── */
function renderPagination() {
  const container = document.getElementById('contractPagination');
  if (!container) return;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);
  if (totalPages <= 1) { container.innerHTML = `<span class="page-info">Toplam: ${totalCount} kayıt</span>`; return; }

  let html = `<span class="page-info">Toplam: ${totalCount} kayıt</span>`;
  html += `<button class="page-btn" onclick="goPage(1)" ${currentPage === 1 ? 'disabled' : ''}>«</button>`;
  html += `<button class="page-btn" onclick="goPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>‹</button>`;

  const start = Math.max(1, currentPage - 2);
  const end   = Math.min(totalPages, currentPage + 2);
  for (let p = start; p <= end; p++) {
    html += `<button class="page-btn ${p === currentPage ? 'active' : ''}" onclick="goPage(${p})">${p}</button>`;
  }
  html += `<button class="page-btn" onclick="goPage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>›</button>`;
  html += `<button class="page-btn" onclick="goPage(${totalPages})" ${currentPage === totalPages ? 'disabled' : ''}>»</button>`;
  container.innerHTML = html;
}

function goPage(p) {
  currentPage = p;
  loadContracts();
}

/* ── Modal ── */
async function openContractModal(id = null) {
  contractEditId = id;
  document.getElementById('contractModalTitle').textContent = id ? 'Sözleşme Düzenle' : 'Yeni Sözleşme';
  clearContractForm();

  if (id) {
    const c = contractRows.find(x => x.id === id);
    if (c) fillContractForm(c);
    else {
      try {
        const data = await api(`/api/contracts/${id}`);
        fillContractForm(data);
      } catch (e) { showToast(e.message, 'error'); return; }
    }
  }
  document.getElementById('contractModal').classList.add('open');
}

function closeContractModal() {
  document.getElementById('contractModal').classList.remove('open');
  contractEditId = null;
}

function clearContractForm() {
  const ids = ['c_contract_number','c_contract_name','c_start_date','c_end_date','c_signed_date',
    'c_renewal_date','c_amount','c_termination_notice_days','c_responsible_person_name',
    'c_responsible_person_email','c_responsible_person_username','c_responsible_department',
    'c_description','c_internal_notes','c_tags'];
  ids.forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  const selects = ['c_institution_id','c_contract_type_id','c_currency_id','c_payment_period'];
  selects.forEach(id => { const el = document.getElementById(id); if (el) el.selectedIndex = 0; });
  document.getElementById('c_status').value       = 'Taslak';
  document.getElementById('c_critical_level').value = 'Düşük';
  document.getElementById('c_reminder_days').value  = '30';
  document.getElementById('c_vat_included').checked  = false;
  document.getElementById('c_auto_renewal').checked  = false;
  document.getElementById('responsibleDropdown').style.display = 'none';
}

function fillContractForm(c) {
  const set = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined && val !== null) el.value = val; };
  set('c_contract_number',          c.contract_number);
  set('c_contract_name',            c.contract_name);
  set('c_institution_id',           c.institution_id);
  set('c_contract_type_id',         c.contract_type_id || '');
  set('c_start_date',               c.start_date || '');
  set('c_end_date',                 c.end_date || '');
  set('c_signed_date',              c.signed_date || '');
  set('c_renewal_date',             c.renewal_date || '');
  set('c_amount',                   c.amount || '');
  set('c_currency_id',              c.currency_id || '');
  set('c_payment_period',           c.payment_period || '');
  set('c_status',                   c.status);
  set('c_critical_level',           c.critical_level);
  set('c_reminder_days',            c.reminder_days);
  set('c_termination_notice_days',  c.termination_notice_days || '');
  set('c_responsible_person_name',  c.responsible_person_name || '');
  set('c_responsible_person_email', c.responsible_person_email || '');
  set('c_responsible_person_username', c.responsible_person_username || '');
  set('c_responsible_department',   c.responsible_department || '');
  set('c_description',              c.description || '');
  set('c_internal_notes',           c.internal_notes || '');
  set('c_tags',                     (c.tags || []).join(', '));
  document.getElementById('c_vat_included').checked = !!c.vat_included;
  document.getElementById('c_auto_renewal').checked = !!c.auto_renewal;
}

/* ── Save ── */
async function saveContract() {
  const btn = document.getElementById('contractSaveBtn');
  btn.disabled = true;
  btn.textContent = 'Kaydediliyor…';

  const payload = {
    contract_number:          document.getElementById('c_contract_number').value.trim(),
    contract_name:            document.getElementById('c_contract_name').value.trim(),
    institution_id:           Number(document.getElementById('c_institution_id').value) || null,
    contract_type_id:         Number(document.getElementById('c_contract_type_id').value) || null,
    start_date:               document.getElementById('c_start_date').value || null,
    end_date:                 document.getElementById('c_end_date').value || null,
    signed_date:              document.getElementById('c_signed_date').value || null,
    renewal_date:             document.getElementById('c_renewal_date').value || null,
    amount:                   document.getElementById('c_amount').value ? Number(document.getElementById('c_amount').value) : null,
    currency_id:              Number(document.getElementById('c_currency_id').value) || null,
    vat_included:             document.getElementById('c_vat_included').checked,
    payment_period:           document.getElementById('c_payment_period').value || null,
    status:                   document.getElementById('c_status').value,
    critical_level:           document.getElementById('c_critical_level').value,
    reminder_days:            Number(document.getElementById('c_reminder_days').value) || 30,
    auto_renewal:             document.getElementById('c_auto_renewal').checked,
    termination_notice_days:  document.getElementById('c_termination_notice_days').value ? Number(document.getElementById('c_termination_notice_days').value) : null,
    responsible_person_name:  document.getElementById('c_responsible_person_name').value.trim() || null,
    responsible_person_email: document.getElementById('c_responsible_person_email').value.trim() || null,
    responsible_person_username: document.getElementById('c_responsible_person_username').value.trim() || null,
    responsible_department:   document.getElementById('c_responsible_department').value.trim() || null,
    description:              document.getElementById('c_description').value.trim() || null,
    internal_notes:           document.getElementById('c_internal_notes').value.trim() || null,
    tags:                     document.getElementById('c_tags').value.split(',').map(t => t.trim()).filter(Boolean),
  };

  try {
    if (contractEditId) {
      await api(`/api/contracts/${contractEditId}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Sözleşme güncellendi', 'success');
    } else {
      await api('/api/contracts', { method: 'POST', body: JSON.stringify(payload) });
      showToast('Sözleşme oluşturuldu', 'success');
    }
    closeContractModal();
    currentPage = 1;
    loadContracts();
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Kaydet';
  }
}

/* ── Delete ── */
async function deleteContract(id) {
  const confirmed = await showConfirm('Bu sözleşmeyi silmek istediğinizden emin misiniz? Bu işlem geri alınamaz.', 'Sözleşme Sil');
  if (!confirmed) return;
  try {
    await api(`/api/contracts/${id}`, { method: 'DELETE', body: JSON.stringify({}) });
    showToast('Sözleşme silindi', 'success');
    loadContracts();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

/* ── LDAP Autocomplete ── */
async function responsibleSearch(val) {
  const dropdown = document.getElementById('responsibleDropdown');
  if (val.length < 2) { dropdown.style.display = 'none'; return; }

  clearTimeout(ldapTimer);
  ldapTimer = setTimeout(async () => {
    dropdown.style.display = '';
    dropdown.innerHTML = '<div class="autocomplete-loading">Aranıyor…</div>';
    try {
      const results = await api(`/api/contracts/responsible-search?q=${encodeURIComponent(val)}`);
      if (!results || results.length === 0) {
        dropdown.innerHTML = '<div class="autocomplete-empty">Sonuç bulunamadı (Manuel giriş yapabilirsiniz)</div>';
        return;
      }
      dropdown.innerHTML = results.map((r, i) => `
        <div class="autocomplete-item" onclick="selectResponsible(${i})" data-index="${i}"
             data-name="${escHtml(r.display_name || r.full_name || r.name || '')}"
             data-email="${escHtml(r.email || '')}"
             data-username="${escHtml(r.username || r.samaccountname || '')}"
             data-dept="${escHtml(r.department || '')}">
          <div class="ac-name">${escHtml(r.display_name || r.full_name || r.name || r.username)}</div>
          <div class="ac-sub">${escHtml([r.title, r.department, r.email].filter(Boolean).join(' · '))}</div>
        </div>`).join('');
    } catch {
      dropdown.innerHTML = '<div class="autocomplete-empty">AD bağlantısı yok, manuel giriş yapabilirsiniz</div>';
    }
  }, 350);
}

function selectResponsible(index) {
  const item = document.querySelector(`#responsibleDropdown [data-index="${index}"]`);
  if (!item) return;
  document.getElementById('c_responsible_person_name').value     = item.dataset.name;
  document.getElementById('c_responsible_person_email').value    = item.dataset.email;
  document.getElementById('c_responsible_person_username').value = item.dataset.username;
  document.getElementById('c_responsible_department').value      = item.dataset.dept;
  document.getElementById('responsibleDropdown').style.display   = 'none';
}

/* ── Documents ── */
async function openDocModal(contractId, contractName) {
  currentDocContractId = contractId;
  document.getElementById('docModalTitle').textContent = `Belgeler — ${contractName}`;
  document.getElementById('documentModal').classList.add('open');
  await loadDocuments(contractId);
}

function closeDocModal() {
  document.getElementById('documentModal').classList.remove('open');
  currentDocContractId = null;
}

async function loadDocuments(contractId) {
  const list = document.getElementById('docList');
  list.innerHTML = '<div style="color:var(--muted);font-size:13px;text-align:center;padding:16px"><div class="spinner"></div></div>';
  try {
    const docs = await api(`/api/documents/contract/${contractId}`);
    if (docs.length === 0) {
      list.innerHTML = '<div class="empty-state" style="padding:20px"><div class="empty-icon">📎</div><p>Belge yüklenmemiş</p></div>';
      return;
    }
    const fileIcons = { 'pdf': '📕', 'doc': '📘', 'docx': '📘', 'xls': '📗', 'xlsx': '📗', 'png': '🖼', 'jpg': '🖼', 'jpeg': '🖼' };
    const isAdmin = window.CT_APP.role === 'admin';
    list.innerHTML = docs.map(d => {
      const ext = d.original_filename.split('.').pop().toLowerCase();
      const icon = fileIcons[ext] || '📄';
      const sizeMb = d.size_bytes < 1024*1024 ? (d.size_bytes / 1024).toFixed(0) + ' KB' : (d.size_bytes / 1024 / 1024).toFixed(1) + ' MB';
      return `
        <div class="doc-item">
          <span class="doc-icon">${icon}</span>
          <div class="doc-info">
            <div class="doc-name">${escHtml(d.original_filename)}</div>
            <div class="doc-meta">${sizeMb} · ${formatDate(d.uploaded_at)}</div>
          </div>
          <div style="display:flex;gap:6px">
            <a href="/api/documents/${d.id}/download" class="btn btn-xs btn-secondary" target="_blank">İndir</a>
            ${isAdmin ? `<button class="btn btn-xs btn-danger" onclick="deleteDocument(${d.id})">Sil</button>` : ''}
          </div>
        </div>`;
    }).join('');
  } catch (e) {
    list.innerHTML = `<div class="alert alert-error">${escHtml(e.message)}</div>`;
  }
}

async function uploadDocument() {
  const fileInput = document.getElementById('docFileInput');
  const progress  = document.getElementById('uploadProgress');
  if (!fileInput.files || fileInput.files.length === 0) { showToast('Dosya seçiniz', 'warn'); return; }

  const fd = new FormData();
  fd.append('file', fileInput.files[0]);

  progress.style.display = '';
  try {
    await api(`/api/documents/contract/${currentDocContractId}`, { method: 'POST', body: fd });
    showToast('Belge yüklendi', 'success');
    fileInput.value = '';
    await loadDocuments(currentDocContractId);
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    progress.style.display = 'none';
  }
}

async function deleteDocument(docId) {
  const confirmed = await showConfirm('Bu belgeyi silmek istediğinizden emin misiniz?', 'Belge Sil');
  if (!confirmed) return;
  try {
    await api(`/api/documents/${docId}`, { method: 'DELETE', body: JSON.stringify({}) });
    showToast('Belge silindi', 'success');
    await loadDocuments(currentDocContractId);
  } catch (e) {
    showToast(e.message, 'error');
  }
}

/* ── Init ── */
async function loadDropdowns() {
  try {
    const [institutions, types, currencies] = await Promise.all([
      api('/api/institutions?page_size=500'),
      api('/api/contracts/types'),
      api('/api/contracts/currencies'),
    ]);

    const instFilter = document.getElementById('institutionFilter');
    const instSelect = document.getElementById('c_institution_id');
    const instOpts = institutions.items.map(i => `<option value="${i.id}">${escHtml(i.name)}</option>`).join('');
    instFilter.innerHTML = '<option value="">Tüm Kurumlar</option>' + instOpts;
    instSelect.innerHTML = '<option value="">Kurum seçiniz</option>' + instOpts;

    const typeFilter = document.getElementById('typeFilter');
    const typeSelect = document.getElementById('c_contract_type_id');
    const typeOpts = types.map(t => `<option value="${t.id}">${escHtml(t.name)}</option>`).join('');
    typeFilter.innerHTML = '<option value="">Tüm Türler</option>' + typeOpts;
    typeSelect.innerHTML = '<option value="">Tür seçiniz</option>' + typeOpts;

    const currSelect = document.getElementById('c_currency_id');
    currSelect.innerHTML = '<option value="">Para birimi seçiniz</option>' +
      currencies.map(c => `<option value="${c.id}">${escHtml(c.code)} — ${escHtml(c.name)}</option>`).join('');
  } catch (e) {
    showToast('Dropdown verileri yüklenemedi: ' + e.message, 'error');
  }
}

/* Close dropdown when clicking outside */
document.addEventListener('click', e => {
  if (!e.target.closest('.autocomplete-wrap')) {
    document.getElementById('responsibleDropdown').style.display = 'none';
  }
  if (!e.target.closest('.column-picker')) {
    closeContractColumnMenu();
  }
});

document.addEventListener('DOMContentLoaded', async () => {
  initContractColumnChooser();
  await loadDropdowns();

  /* URL paramları varsa uygula (dashboard linki) */
  const params = new URLSearchParams(location.search);
  if (params.get('sort_by'))    sortField = params.get('sort_by');
  if (params.get('sort_dir'))   sortDir   = params.get('sort_dir');

  await loadContracts();
  updateSortHeaders();
});
