let institutions = [];
let editId = null;

function openInstitutionModal(item = null) {
  editId = item?.id || null;
  document.getElementById('institutionModal').classList.add('open');
  document.getElementById('i_name').value = item?.name || '';
  document.getElementById('i_short_name').value = item?.short_name || '';
  document.getElementById('i_contact_person').value = item?.contact_person || '';
  document.getElementById('i_contact_email').value = item?.contact_email || '';
  document.getElementById('i_description').value = item?.description || '';
}
function closeInstitutionModal() { document.getElementById('institutionModal').classList.remove('open'); }
function findInstitution(id) { return institutions.find(x => x.id === id); }

async function loadInstitutions() {
  const q = document.getElementById('q').value || '';
  const data = await api('/api/institutions?q=' + encodeURIComponent(q));
  institutions = data.items;
  const tbody = document.querySelector('#institutionTable tbody');
  tbody.innerHTML = institutions.map(i => `<tr><td>${i.name}</td><td>${i.short_name || ''}</td><td>${i.contact_person || ''}</td><td>${i.is_active ? 'Aktif' : 'Pasif'}</td><td>${window.CT_APP.role === 'admin' ? `<button class='btn' onclick='openInstitutionModal(findInstitution(${i.id}))'>Düzenle</button> <button class='btn btn-danger' onclick='deleteInstitution(${i.id})'>Sil</button>` : '-'}</td></tr>`).join('');
}

async function saveInstitution() {
  const payload = {
    name: document.getElementById('i_name').value,
    short_name: document.getElementById('i_short_name').value,
    contact_person: document.getElementById('i_contact_person').value,
    contact_email: document.getElementById('i_contact_email').value,
    description: document.getElementById('i_description').value,
    is_active: true
  };
  if (editId) {
    await api('/api/institutions/' + editId, { method: 'PUT', body: JSON.stringify(payload) });
  } else {
    await api('/api/institutions', { method: 'POST', body: JSON.stringify(payload) });
  }
  closeInstitutionModal();
  loadInstitutions();
}
async function deleteInstitution(id) {
  if (!confirm('Kurum silinsin mi?')) return;
  await api('/api/institutions/' + id, { method: 'DELETE', body: JSON.stringify({}) });
  loadInstitutions();
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('q').addEventListener('input', () => loadInstitutions());
  loadInstitutions().catch(e => showToast(e.message, 'error'));
});
