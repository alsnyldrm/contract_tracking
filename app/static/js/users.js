let allUsers = [];
let roleChangeUserId = null;

function authSourceLabel(src) {
  const map = { local: 'Yerel', ldap: 'LDAP / AD', saml: 'SAML / SSO' };
  return map[src] || src;
}

async function loadUsers() {
  const tbody = document.getElementById('userTbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="8"><div class="spinner"></div></td></tr>';
  try {
    allUsers = await api('/api/users');
    renderUsers(allUsers);
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="8" class="td-muted" style="text-align:center;padding:24px">${escHtml(e.message)}</td></tr>`;
  }
}

function filterUsers() {
  const q      = document.getElementById('userSearch').value.toLowerCase();
  const role   = document.getElementById('roleFilter').value;
  const source = document.getElementById('sourceFilter').value;

  const filtered = allUsers.filter(u => {
    const matchQ      = !q || u.username.toLowerCase().includes(q) || u.full_name.toLowerCase().includes(q) || (u.email || '').toLowerCase().includes(q);
    const matchRole   = !role   || u.role === role;
    const matchSource = !source || u.auth_source === source;
    return matchQ && matchRole && matchSource;
  });
  renderUsers(filtered);
}

function renderUsers(users) {
  const tbody = document.getElementById('userTbody');
  if (users.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><div class="empty-icon">👥</div><p style="font-weight:600">Kullanıcı bulunamadı</p></div></td></tr>`;
    return;
  }

  tbody.innerHTML = users.map(u => {
    const roleBadge = u.role === 'admin'
      ? '<span class="badge badge-blue">Yönetici</span>'
      : '<span class="badge badge-gray">Salt Okunur</span>';

    const sourceBadge = u.auth_source === 'saml'
      ? '<span class="badge badge-purple">SAML / SSO</span>'
      : u.auth_source === 'ldap'
      ? '<span class="badge badge-yellow">LDAP / AD</span>'
      : '<span class="badge badge-blue">Yerel</span>';

    const activeBadge = u.is_active
      ? '<span class="badge badge-green">Aktif</span>'
      : '<span class="badge badge-red">Pasif</span>';

    const mustChangeWarning = u.must_change_password
      ? '<span title="Şifre değiştirmesi gerekiyor" style="margin-left:4px;color:var(--warning)">⚠</span>' : '';

    return `<tr>
      <td style="font-weight:600">${escHtml(u.username)}${mustChangeWarning}</td>
      <td>
        <div style="display:flex;align-items:center;gap:8px">
          <div style="width:30px;height:30px;border-radius:50%;background:var(--primary-light);
                      color:var(--primary);display:flex;align-items:center;justify-content:center;
                      font-weight:700;font-size:13px;flex-shrink:0">
            ${escHtml((u.full_name || '?')[0].toUpperCase())}
          </div>
          <span>${escHtml(u.full_name)}</span>
        </div>
      </td>
      <td style="font-size:12.5px">${u.email ? `<a href="mailto:${escHtml(u.email)}" style="color:var(--primary)">${escHtml(u.email)}</a>` : '—'}</td>
      <td>${roleBadge}</td>
      <td>${sourceBadge}</td>
      <td>${activeBadge}</td>
      <td class="td-muted" style="font-size:12px">${formatDate(u.created_at)}</td>
      <td>
        <button class="btn btn-sm btn-secondary" onclick="openRoleModal(${u.id}, '${escHtml(u.username)}', '${u.role}')">
          Rol Değiştir
        </button>
      </td>
    </tr>`;
  }).join('');
}

/* ── Role modal ── */
function openRoleModal(userId, username, currentRole) {
  roleChangeUserId = userId;
  document.getElementById('roleModalUser').textContent = username;
  document.getElementById('roleModalSelect').value = currentRole;
  document.getElementById('roleModal').classList.add('open');
}

async function applyRoleChange() {
  if (!roleChangeUserId) return;
  const role = document.getElementById('roleModalSelect').value;
  try {
    await api(`/api/users/${roleChangeUserId}/role`, { method: 'PUT', body: JSON.stringify({ role }) });
    showToast('Rol güncellendi', 'success');
    document.getElementById('roleModal').classList.remove('open');
    roleChangeUserId = null;
    await loadUsers();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function changeRole(id, role) {
  try {
    await api(`/api/users/${id}/role`, { method: 'PUT', body: JSON.stringify({ role }) });
    showToast('Rol güncellendi', 'success');
    await loadUsers();
  } catch (e) { showToast(e.message, 'error'); }
}

document.addEventListener('DOMContentLoaded', () => loadUsers().catch(e => showToast(e.message, 'error')));
