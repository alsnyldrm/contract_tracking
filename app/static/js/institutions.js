let editId      = null;
let instRows    = [];
let instPage    = 1;
let instTotal   = 0;
const INST_PAGE_SIZE = 20;
let instDebounce = null;

function debounceInst() {
  clearTimeout(instDebounce);
  instDebounce = setTimeout(loadInstitutions, 400);
}

function resetInstFilters() {
  document.getElementById('q').value = '';
  document.getElementById('typeFilter').value = '';
  document.getElementById('activeFilter').value = '';
  instPage = 1;
  loadInstitutions();
}

function findInstitution(id) { return instRows.find(x => x.id === id); }

async function loadInstitutions() {
  const params = new URLSearchParams({
    q:         document.getElementById('q').value || '',
    page:      instPage,
    page_size: INST_PAGE_SIZE,
  });
  const active = document.getElementById('activeFilter').value;
  if (active) params.set('is_active', active);

  const tbody = document.getElementById('institutionTbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="9"><div class="spinner"></div></td></tr>';

  let data;
  try {
    data = await api('/api/institutions?' + params.toString());
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="9" class="td-muted" style="text-align:center;padding:24px">${escHtml(e.message)}</td></tr>`;
    return;
  }

  instRows  = data.items;
  instTotal = data.total;

  if (instRows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state"><div class="empty-icon">🏛</div><p style="font-weight:600">Kurum bulunamadı</p></div></td></tr>`;
    renderInstPagination();
    return;
  }

  const isAdmin = window.CT_APP.role === 'admin';
  tbody.innerHTML = instRows.map(i => `
    <tr>
      <td style="font-weight:600">${escHtml(i.name)}</td>
      <td class="td-muted">${escHtml(i.short_name || '—')}</td>
      <td>${escHtml(i.institution_type_name || '—')}</td>
      <td class="td-muted" style="font-size:12.5px">${escHtml(i.tax_no || '—')}</td>
      <td>${escHtml(i.contact_person || '—')}</td>
      <td style="font-size:12.5px">${i.contact_email ? `<a href="mailto:${escHtml(i.contact_email)}" style="color:var(--primary)">${escHtml(i.contact_email)}</a>` : '—'}</td>
      <td class="td-muted" style="font-size:12.5px">${escHtml(i.contact_phone || '—')}</td>
      <td>${i.is_active ? '<span class="badge badge-green">Aktif</span>' : '<span class="badge badge-gray">Pasif</span>'}</td>
      <td>
        <div class="table-actions">
          ${isAdmin ? `
          <button class="btn btn-sm btn-secondary" onclick="openInstitutionModal(${i.id})">✏</button>
          <button class="btn btn-sm btn-danger" onclick="deleteInstitution(${i.id})">🗑</button>
          ` : '<span class="td-muted" style="font-size:12px">—</span>'}
        </div>
      </td>
    </tr>`).join('');

  renderInstPagination();
}

function renderInstPagination() {
  const container = document.getElementById('instPagination');
  if (!container) return;
  const totalPages = Math.ceil(instTotal / INST_PAGE_SIZE);
  if (totalPages <= 1) { container.innerHTML = `<span class="page-info">Toplam: ${instTotal} kurum</span>`; return; }

  let html = `<span class="page-info">Toplam: ${instTotal} kurum</span>`;
  html += `<button class="page-btn" onclick="instGoPage(1)" ${instPage===1?'disabled':''}>«</button>`;
  html += `<button class="page-btn" onclick="instGoPage(${instPage-1})" ${instPage===1?'disabled':''}>‹</button>`;
  const start = Math.max(1, instPage - 2);
  const end   = Math.min(totalPages, instPage + 2);
  for (let p = start; p <= end; p++) {
    html += `<button class="page-btn ${p===instPage?'active':''}" onclick="instGoPage(${p})">${p}</button>`;
  }
  html += `<button class="page-btn" onclick="instGoPage(${instPage+1})" ${instPage===totalPages?'disabled':''}>›</button>`;
  html += `<button class="page-btn" onclick="instGoPage(${totalPages})" ${instPage===totalPages?'disabled':''}>»</button>`;
  container.innerHTML = html;
}

function instGoPage(p) {
  instPage = p;
  loadInstitutions();
}

/* ── Modal ── */
async function openInstitutionModal(id = null) {
  editId = id;
  document.getElementById('instModalTitle').textContent = id ? 'Kurum Düzenle' : 'Yeni Kurum';
  clearInstForm();

  if (id) {
    const item = findInstitution(id);
    if (item) fillInstForm(item);
  }

  document.getElementById('institutionModal').classList.add('open');
}

function closeInstitutionModal() {
  document.getElementById('institutionModal').classList.remove('open');
  editId = null;
}

function clearInstForm() {
  ['i_name','i_short_name','i_tax_no','i_tax_office','i_sector',
   'i_contact_person','i_contact_email','i_contact_phone','i_address','i_description']
    .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  document.getElementById('i_institution_type_id').value = '';
  document.getElementById('i_is_active').checked = true;
}

function fillInstForm(item) {
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
  set('i_name',                item.name);
  set('i_short_name',          item.short_name);
  set('i_tax_no',              item.tax_no);
  set('i_tax_office',          item.tax_office);
  set('i_sector',              item.sector);
  set('i_contact_person',      item.contact_person);
  set('i_contact_email',       item.contact_email);
  set('i_contact_phone',       item.contact_phone);
  set('i_address',             item.address);
  set('i_description',         item.description);
  set('i_institution_type_id', item.institution_type_id || '');
  document.getElementById('i_is_active').checked = !!item.is_active;
}

async function saveInstitution() {
  const btn = document.getElementById('instSaveBtn');
  btn.disabled = true;
  btn.textContent = 'Kaydediliyor…';

  const payload = {
    name:                 document.getElementById('i_name').value.trim(),
    short_name:           document.getElementById('i_short_name').value.trim() || null,
    tax_no:               document.getElementById('i_tax_no').value.trim() || null,
    tax_office:           document.getElementById('i_tax_office').value.trim() || null,
    institution_type_id:  Number(document.getElementById('i_institution_type_id').value) || null,
    sector:               document.getElementById('i_sector').value.trim() || null,
    contact_person:       document.getElementById('i_contact_person').value.trim() || null,
    contact_email:        document.getElementById('i_contact_email').value.trim() || null,
    contact_phone:        document.getElementById('i_contact_phone').value.trim() || null,
    address:              document.getElementById('i_address').value.trim() || null,
    description:          document.getElementById('i_description').value.trim() || null,
    is_active:            document.getElementById('i_is_active').checked,
  };

  if (!payload.name) { showToast('Kurum adı zorunludur', 'error'); btn.disabled = false; btn.textContent = 'Kaydet'; return; }

  try {
    if (editId) {
      await api(`/api/institutions/${editId}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Kurum güncellendi', 'success');
    } else {
      await api('/api/institutions', { method: 'POST', body: JSON.stringify(payload) });
      showToast('Kurum oluşturuldu', 'success');
    }
    closeInstitutionModal();
    loadInstitutions();
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Kaydet';
  }
}

async function deleteInstitution(id) {
  const item = findInstitution(id);
  const name = item?.name || 'Bu kurum';
  const confirmed = await showConfirm(`"${name}" kurumunu silmek istediğinizden emin misiniz?`, 'Kurum Sil');
  if (!confirmed) return;
  try {
    await api(`/api/institutions/${id}`, { method: 'DELETE', body: JSON.stringify({}) });
    showToast('Kurum silindi', 'success');
    loadInstitutions();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function loadInstTypes() {
  try {
    const types = await api('/api/institutions/types');
    const typeFilter = document.getElementById('typeFilter');
    const typeSelect = document.getElementById('i_institution_type_id');
    const opts = types.map(t => `<option value="${t.id}">${escHtml(t.name)}</option>`).join('');
    typeFilter.innerHTML = '<option value="">Tüm Tipler</option>' + opts;
    typeSelect.innerHTML = '<option value="">Tip seçiniz</option>' + opts;
  } catch { /* sessiz */ }
}

document.addEventListener('DOMContentLoaded', async () => {
  await loadInstTypes();
  await loadInstitutions();
});
