let contractEditId = null;
let contractRows = [];
let institutions = [];
function findContract(id) { return contractRows.find(x => x.id === id); }

function openContractModal(item = null) {
  contractEditId = item?.id || null;
  document.getElementById('contractModal').classList.add('open');
  document.getElementById('c_contract_number').value = item?.contract_number || '';
  document.getElementById('c_contract_name').value = item?.contract_name || '';
  document.getElementById('c_status').value = item?.status || 'Taslak';
  document.getElementById('c_critical_level').value = item?.critical_level || 'Düşük';
  document.getElementById('c_end_date').value = item?.end_date || '';
  document.getElementById('c_responsible_person_name').value = item?.responsible_person_name || '';
  document.getElementById('c_tags').value = item?.tags || '';
  if (item?.institution_id) document.getElementById('c_institution_id').value = item.institution_id;
}
function closeContractModal() { document.getElementById('contractModal').classList.remove('open'); }

async function loadInstitutionOptions() {
  const data = await api('/api/institutions?page_size=200');
  institutions = data.items;
  const sel = document.getElementById('c_institution_id');
  sel.innerHTML = institutions.map(i => `<option value='${i.id}'>${i.name}</option>`).join('');
}

async function loadContracts() {
  const q = document.getElementById('search').value || '';
  const status = document.getElementById('statusFilter').value || '';
  const data = await api(`/api/contracts?q=${encodeURIComponent(q)}&status=${encodeURIComponent(status)}`);
  contractRows = data.items;
  const tbody = document.querySelector('#contractTable tbody');
  tbody.innerHTML = contractRows.map(c => `<tr><td>${c.contract_number}</td><td>${c.institution_name || ''}</td><td>${c.contract_name}</td><td>${c.status}</td><td>${c.critical_level}</td><td>${c.end_date || ''}</td><td>${window.CT_APP.role === 'admin' ? `<button class='btn' onclick='openContractModal(findContract(${c.id}))'>Düzenle</button> <button class='btn btn-danger' onclick='deleteContract(${c.id})'>Sil</button>` : `<a class='btn' href='/api/documents/contract/${c.id}' target='_blank'>Belgeler</a>`}</td></tr>`).join('');
}

async function saveContract() {
  const payload = {
    contract_number: document.getElementById('c_contract_number').value,
    contract_name: document.getElementById('c_contract_name').value,
    institution_id: Number(document.getElementById('c_institution_id').value),
    status: document.getElementById('c_status').value,
    critical_level: document.getElementById('c_critical_level').value,
    end_date: document.getElementById('c_end_date').value || null,
    responsible_person_name: document.getElementById('c_responsible_person_name').value,
    tags: document.getElementById('c_tags').value,
    description: document.getElementById('c_description').value
  };
  if (contractEditId) {
    await api('/api/contracts/' + contractEditId, { method: 'PUT', body: JSON.stringify(payload) });
  } else {
    await api('/api/contracts', { method: 'POST', body: JSON.stringify(payload) });
  }
  closeContractModal();
  loadContracts();
}

async function deleteContract(id) {
  if (!confirm('Sözleşme silinsin mi?')) return;
  await api('/api/contracts/' + id, { method: 'DELETE', body: JSON.stringify({}) });
  loadContracts();
}

document.addEventListener('DOMContentLoaded', async () => {
  await loadInstitutionOptions();
  await loadContracts();
  document.getElementById('search').addEventListener('input', () => loadContracts());
  document.getElementById('statusFilter').addEventListener('change', () => loadContracts());
});
