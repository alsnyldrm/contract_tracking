let notificationGroupRows = [];
let notificationUsers = [];
let ngEditId = null;
let ngSelectedUserIds = new Set();

async function loadNotificationGroups() {
  const tbody = document.getElementById('ngTbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="7"><div class="spinner"></div></td></tr>';

  try {
    notificationGroupRows = await api('/api/notification-groups');
    renderNotificationGroups(notificationGroupRows);
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" class="td-muted" style="text-align:center;padding:24px">${escHtml(e.message)}</td></tr>`;
  }
}

async function loadNotificationUsers() {
  notificationUsers = await api('/api/notification-groups/users');
}

function renderNotificationGroups(rows) {
  const tbody = document.getElementById('ngTbody');
  if (!rows || rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">📣</div><p style="font-weight:600">Bildirim grubu bulunamadı</p></div></td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(g => {
    const members = g.members || [];
    const memberText = members.map(m => m.full_name || m.username).join(', ');
    return `
      <tr>
        <td style="font-weight:600">${escHtml(g.name)}</td>
        <td class="td-truncate" style="max-width:240px" title="${escHtml(g.description || '')}">${escHtml(g.description || '—')}</td>
        <td class="td-nowrap">${g.member_count || 0}</td>
        <td class="td-truncate" style="max-width:360px" title="${escHtml(memberText)}">${escHtml(memberText || '—')}</td>
        <td>${g.is_active ? '<span class="badge badge-green">Aktif</span>' : '<span class="badge badge-gray">Pasif</span>'}</td>
        <td class="td-nowrap td-muted" style="font-size:12px">${formatDate(g.updated_at)}</td>
        <td>
          <div class="table-actions">
            <button class="btn btn-sm btn-secondary" onclick="openNotificationGroupModal(${g.id})">✏</button>
            <button class="btn btn-sm btn-danger" onclick="deleteNotificationGroup(${g.id})">🗑</button>
          </div>
        </td>
      </tr>`;
  }).join('');
}

function filterNotificationGroups() {
  const q = (document.getElementById('ngSearch').value || '').toLowerCase().trim();
  const status = document.getElementById('ngStatusFilter').value;

  const filtered = notificationGroupRows.filter(g => {
    const members = (g.members || []).map(m => `${m.username} ${m.full_name} ${m.email || ''}`.toLowerCase()).join(' ');
    const text = `${g.name || ''} ${g.description || ''} ${members}`.toLowerCase();
    const matchQ = !q || text.includes(q);
    const matchStatus = !status || (status === 'active' ? g.is_active : !g.is_active);
    return matchQ && matchStatus;
  });

  renderNotificationGroups(filtered);
}

function resetNotificationGroupFilters() {
  document.getElementById('ngSearch').value = '';
  document.getElementById('ngStatusFilter').value = '';
  filterNotificationGroups();
}

function clearNotificationGroupForm() {
  document.getElementById('ng_name').value = '';
  document.getElementById('ng_description').value = '';
  document.getElementById('ng_is_active').checked = true;
  document.getElementById('ngUserSearchInput').value = '';
  ngSelectedUserIds = new Set();
  renderNotificationGroupUserOptions();
}

function openNotificationGroupModal(groupId = null) {
  ngEditId = groupId;
  document.getElementById('ngModalTitle').textContent = groupId ? 'Bildirim Grubunu Düzenle' : 'Yeni Bildirim Grubu';
  clearNotificationGroupForm();

  if (groupId) {
    const row = notificationGroupRows.find(x => x.id === groupId);
    if (row) {
      document.getElementById('ng_name').value = row.name || '';
      document.getElementById('ng_description').value = row.description || '';
      document.getElementById('ng_is_active').checked = !!row.is_active;
      ngSelectedUserIds = new Set((row.members || []).map(m => m.id));
      renderNotificationGroupUserOptions();
    }
  }

  document.getElementById('notificationGroupModal').classList.add('open');
}

function closeNotificationGroupModal() {
  document.getElementById('notificationGroupModal').classList.remove('open');
  ngEditId = null;
}

function renderNotificationGroupUserOptions() {
  const container = document.getElementById('ngUserOptions');
  const q = (document.getElementById('ngUserSearchInput').value || '').toLowerCase().trim();
  if (!container) return;

  const filtered = notificationUsers.filter(u => {
    const text = `${u.username} ${u.full_name} ${u.email || ''}`.toLowerCase();
    return !q || text.includes(q);
  });

  if (filtered.length === 0) {
    container.innerHTML = '<div class="td-muted" style="padding:8px 6px;text-align:center">Kullanıcı bulunamadı</div>';
    return;
  }

  container.innerHTML = filtered.map(u => {
    const checked = ngSelectedUserIds.has(u.id) ? 'checked' : '';
    return `
      <label class="checkbox-label" style="display:flex;justify-content:space-between;border-bottom:1px solid var(--border);padding:8px 4px">
        <span style="display:flex;align-items:center;gap:8px;min-width:0">
          <input type="checkbox" ${checked} onchange="toggleNotificationGroupUser(${u.id}, this.checked)" />
          <span style="min-width:0">
            <div style="font-weight:600;line-height:1.2">${escHtml(u.full_name || u.username)}</div>
            <div class="td-muted" style="font-size:11.5px;line-height:1.2">${escHtml(u.username)}${u.email ? ' · ' + escHtml(u.email) : ' · e-posta yok'}</div>
          </span>
        </span>
      </label>`;
  }).join('');
}

function toggleNotificationGroupUser(userId, checked) {
  if (checked) ngSelectedUserIds.add(userId);
  else ngSelectedUserIds.delete(userId);
}

async function saveNotificationGroup() {
  const btn = document.getElementById('ngSaveBtn');
  btn.disabled = true;
  btn.textContent = 'Kaydediliyor…';

  const payload = {
    name: document.getElementById('ng_name').value.trim(),
    description: document.getElementById('ng_description').value.trim() || null,
    is_active: document.getElementById('ng_is_active').checked,
    user_ids: Array.from(ngSelectedUserIds),
  };

  if (!payload.name) {
    showToast('Grup adı zorunludur', 'error');
    btn.disabled = false;
    btn.textContent = 'Kaydet';
    return;
  }

  if (payload.user_ids.length === 0) {
    showToast('En az bir kullanıcı seçmelisiniz', 'error');
    btn.disabled = false;
    btn.textContent = 'Kaydet';
    return;
  }

  try {
    if (ngEditId) {
      await api(`/api/notification-groups/${ngEditId}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Bildirim grubu güncellendi', 'success');
    } else {
      await api('/api/notification-groups', { method: 'POST', body: JSON.stringify(payload) });
      showToast('Bildirim grubu oluşturuldu', 'success');
    }
    closeNotificationGroupModal();
    await loadNotificationGroups();
    filterNotificationGroups();
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Kaydet';
  }
}

async function deleteNotificationGroup(groupId) {
  const row = notificationGroupRows.find(x => x.id === groupId);
  const name = row?.name || 'Bu bildirim grubu';
  const confirmed = await showConfirm(`"${name}" grubunu silmek istediğinizden emin misiniz?`, 'Bildirim Grubu Sil');
  if (!confirmed) return;

  try {
    await api(`/api/notification-groups/${groupId}`, { method: 'DELETE', body: JSON.stringify({}) });
    showToast('Bildirim grubu silindi', 'success');
    await loadNotificationGroups();
    filterNotificationGroups();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  try {
    await loadNotificationUsers();
    await loadNotificationGroups();
  } catch (e) {
    showToast(e.message, 'error');
  }
});
