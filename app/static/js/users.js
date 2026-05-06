let allUsers = [];
let roleChangeUserId = null;
let resetPwUserId = null;
let editUserId = null;

function authSourceLabel(src) {
  const map = { local: 'Yerel', saml: 'SAML / SSO' };
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
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          <button class="btn btn-sm" onclick="openEditUserModal(${u.id})">Düzenle</button>
          <button class="btn btn-sm btn-secondary" onclick="openRoleModal(${u.id}, '${escHtml(u.username)}', '${u.role}')">Rol</button>
          ${u.auth_source === 'local' ? `<button class="btn btn-sm" onclick="openResetPwModal(${u.id}, '${escHtml(u.username)}')">Şifre</button>` : ''}
          <button class="btn btn-sm" onclick="toggleActive(${u.id}, ${!u.is_active})">${u.is_active ? 'Pasifleştir' : 'Aktifleştir'}</button>
          <button class="btn btn-sm btn-danger" onclick="deleteUser(${u.id}, '${escHtml(u.username)}')">Sil</button>
        </div>
      </td>
    </tr>`;
  }).join('');
}

function openEditUserModal(userId) {
  const user = allUsers.find(u => u.id === userId);
  if (!user) {
    showToast('Kullanıcı bulunamadı', 'error');
    return;
  }
  editUserId = userId;
  const usernameInput = document.getElementById('eu_username');
  const usernameHint = document.getElementById('eu_username_hint');
  const fullNameInput = document.getElementById('eu_full_name');
  const emailInput = document.getElementById('eu_email');

  usernameInput.value = user.username || '';
  fullNameInput.value = user.full_name || '';
  emailInput.value = user.email || '';

  const lockUsername = user.auth_source !== 'local';
  usernameInput.disabled = lockUsername;
  usernameHint.style.display = lockUsername ? '' : 'none';

  document.getElementById('editUserModal').classList.add('open');
}

function closeEditUserModal() {
  document.getElementById('editUserModal').classList.remove('open');
  editUserId = null;
}

async function updateUserProfile() {
  if (!editUserId) return;
  const btn = document.getElementById('editUserSaveBtn');
  btn.disabled = true;
  btn.textContent = 'Kaydediliyor…';
  const usernameInput = document.getElementById('eu_username');

  const payload = {
    full_name: document.getElementById('eu_full_name').value.trim(),
    email: document.getElementById('eu_email').value.trim() || null,
  };
  if (!usernameInput.disabled) {
    payload.username = usernameInput.value.trim();
  }

  if (!payload.full_name) {
    showToast('Ad Soyad boş olamaz', 'error');
    btn.disabled = false;
    btn.textContent = 'Kaydet';
    return;
  }

  try {
    await api(`/api/users/${editUserId}`, { method: 'PUT', body: JSON.stringify(payload) });
    showToast('Kullanıcı bilgileri güncellendi', 'success');
    closeEditUserModal();
    await loadUsers();
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Kaydet';
  }
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

/* ── Yeni kullanıcı modal ── */
function openUserModal() {
  document.getElementById('u_username').value = '';
  document.getElementById('u_full_name').value = '';
  document.getElementById('u_email').value = '';
  document.getElementById('u_password').value = '';
  document.getElementById('u_role').value = 'readonly';
  document.getElementById('userModal').classList.add('open');
}
function closeUserModal() { document.getElementById('userModal').classList.remove('open'); }

async function saveUser() {
  const payload = {
    username: document.getElementById('u_username').value.trim(),
    full_name: document.getElementById('u_full_name').value.trim(),
    email: document.getElementById('u_email').value.trim(),
    password: document.getElementById('u_password').value,
    role: document.getElementById('u_role').value,
  };
  if (!payload.username || !payload.full_name || !payload.password) {
    showToast('Kullanıcı adı, ad soyad ve şifre zorunludur', 'error');
    return;
  }
  if (payload.password.length < 8) {
    showToast('Şifre en az 8 karakter olmalı', 'error');
    return;
  }
  try {
    await api('/api/users/', { method: 'POST', body: JSON.stringify(payload) });
    showToast('Kullanıcı oluşturuldu', 'success');
    closeUserModal();
    await loadUsers();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

/* ── Şifre sıfırlama modal ── */
function openResetPwModal(id, username) {
  resetPwUserId = id;
  document.getElementById('resetPwUserLabel').textContent = username;
  document.getElementById('rp_password').value = '';
  document.getElementById('resetPwModal').classList.add('open');
}
function closeResetPwModal() {
  document.getElementById('resetPwModal').classList.remove('open');
  resetPwUserId = null;
}

async function submitResetPw() {
  const password = document.getElementById('rp_password').value;
  if (!password || password.length < 8) {
    showToast('Şifre en az 8 karakter olmalı', 'error');
    return;
  }
  try {
    await api(`/api/users/${resetPwUserId}/reset-password`, { method: 'PUT', body: JSON.stringify({ password }) });
    showToast('Şifre sıfırlandı', 'success');
    closeResetPwModal();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

/* ── Aktif/Pasif ve Silme ── */
async function toggleActive(id, isActive) {
  try {
    await api(`/api/users/${id}/active`, { method: 'PUT', body: JSON.stringify({ is_active: isActive }) });
    showToast(isActive ? 'Kullanıcı aktifleştirildi' : 'Kullanıcı pasifleştirildi', 'success');
    await loadUsers();
  } catch (e) { showToast(e.message, 'error'); }
}

async function deleteUser(id, username) {
  if (!confirm(`"${username}" kullanıcısı silinsin mi?`)) return;
  try {
    await api(`/api/users/${id}`, { method: 'DELETE', body: JSON.stringify({}) });
    showToast('Kullanıcı silindi', 'success');
    await loadUsers();
  } catch (e) { showToast(e.message, 'error'); }
}

document.addEventListener('DOMContentLoaded', () => loadUsers().catch(e => showToast(e.message, 'error')));
