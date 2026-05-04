async function loadUsers() {
  const rows = await api('/api/users');
  const tbody = document.querySelector('#userTable tbody');
  tbody.innerHTML = rows.map(u => `<tr><td>${u.username}</td><td>${u.full_name}</td><td>${u.role}</td><td>${u.auth_source}</td><td><select onchange='changeRole(${u.id}, this.value)'><option value='readonly' ${u.role==='readonly'?'selected':''}>Read Only</option><option value='admin' ${u.role==='admin'?'selected':''}>Admin</option></select></td></tr>`).join('');
}

async function changeRole(id, role) {
  await api(`/api/users/${id}/role`, { method: 'PUT', body: JSON.stringify({ role }) });
  loadUsers();
}

document.addEventListener('DOMContentLoaded', () => loadUsers().catch(e => alert(e.message)));
