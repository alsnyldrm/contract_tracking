let notificationGroupRows = [];
let ngEditId = null;
let ngSelectedMembers = new Map();
let ngSearchResults = [];
let ngSearchTimer = null;
let ngCandidateList = [];

function memberIdentityKey(member) {
  if (member?.id) return `id:${member.id}`;
  if (member?.username) return `u:${String(member.username).toLowerCase()}`;
  if (member?.email) return `e:${String(member.email).toLowerCase()}`;
  return null;
}

function normalizeMember(member) {
  return {
    id: member?.id ? Number(member.id) : null,
    username: (member?.username || '').trim(),
    full_name: (member?.full_name || member?.display_name || '').trim(),
    email: ((member?.email || '').trim().toLowerCase()) || null,
    department: (member?.department || '').trim(),
    title: (member?.title || '').trim(),
    auth_source: member?.auth_source || 'ldap',
  };
}

function addSelectedMember(member) {
  const normalized = normalizeMember(member);
  const key = memberIdentityKey(normalized);
  if (!key) return;
  ngSelectedMembers.set(key, { ...normalized, _key: key });
}

function setSelectedMembers(members) {
  ngSelectedMembers = new Map();
  (members || []).forEach(m => addSelectedMember(m));
}

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
  setSelectedMembers([]);
  ngSearchResults = [];
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
      setSelectedMembers(row.members || []);
      renderNotificationGroupUserOptions();
    }
  }

  document.getElementById('notificationGroupModal').classList.add('open');
}

function closeNotificationGroupModal() {
  document.getElementById('notificationGroupModal').classList.remove('open');
  ngEditId = null;
}

async function handleNotificationGroupMemberSearch() {
  const q = (document.getElementById('ngUserSearchInput').value || '').trim();
  clearTimeout(ngSearchTimer);

  if (q.length < 2) {
    ngSearchResults = [];
    renderNotificationGroupUserOptions();
    return;
  }

  ngSearchTimer = setTimeout(async () => {
    const container = document.getElementById('ngUserOptions');
    if (container) container.innerHTML = '<div class="td-muted" style="padding:8px 6px;text-align:center">AD üzerinde aranıyor…</div>';

    try {
      ngSearchResults = await api(`/api/notification-groups/ad-search?q=${encodeURIComponent(q)}`);
      renderNotificationGroupUserOptions();
    } catch (e) {
      ngSearchResults = [];
      renderNotificationGroupUserOptions();
      showToast('AD araması başarısız: ' + e.message, 'warn');
    }
  }, 300);
}

function renderNotificationGroupUserOptions() {
  const container = document.getElementById('ngUserOptions');
  const q = (document.getElementById('ngUserSearchInput').value || '').toLowerCase().trim();
  if (!container) return;

  const mergedMap = new Map();
  ngSelectedMembers.forEach((value, key) => mergedMap.set(key, value));
  (ngSearchResults || []).forEach(item => {
    const normalized = normalizeMember(item);
    const key = memberIdentityKey(normalized);
    if (!key) return;
    if (!mergedMap.has(key)) {
      mergedMap.set(key, { ...normalized, _key: key });
    }
  });

  let candidates = Array.from(mergedMap.values());
  if (q) {
    candidates = candidates.filter(u => {
      const text = `${u.username || ''} ${u.full_name || ''} ${u.email || ''}`.toLowerCase();
      return text.includes(q);
    });
  }

  candidates.sort((a, b) => {
    const aName = (a.full_name || a.username || '').toLowerCase();
    const bName = (b.full_name || b.username || '').toLowerCase();
    return aName.localeCompare(bName, 'tr');
  });

  ngCandidateList = candidates;

  if (candidates.length === 0) {
    if (q.length < 2) {
      container.innerHTML = '<div class="td-muted" style="padding:8px 6px;text-align:center">AD kullanıcı araması için en az 2 karakter yazın</div>';
    } else {
      container.innerHTML = '<div class="td-muted" style="padding:8px 6px;text-align:center">AD üzerinde kullanıcı bulunamadı</div>';
    }
    return;
  }

  container.innerHTML = candidates.map((u, idx) => {
    const checked = ngSelectedMembers.has(u._key) ? 'checked' : '';
    const badge = (u.auth_source || '').toLowerCase() === 'ldap' ? '<span class="badge badge-yellow" style="margin-left:6px">AD</span>' : '';
    const line2 = [u.username, u.department, u.title, u.email || 'e-posta yok'].filter(Boolean).join(' · ');
    return `
      <label class="checkbox-label" style="display:flex;justify-content:space-between;border-bottom:1px solid var(--border);padding:8px 4px">
        <span style="display:flex;align-items:center;gap:8px;min-width:0">
          <input type="checkbox" ${checked} onchange="toggleNotificationGroupMember(${idx}, this.checked)" />
          <span style="min-width:0">
            <div style="font-weight:600;line-height:1.2">${escHtml(u.full_name || u.username || u.email || 'AD Kullanıcı')} ${badge}</div>
            <div class="td-muted" style="font-size:11.5px;line-height:1.2">${escHtml(line2)}</div>
          </span>
        </span>
      </label>`;
  }).join('');
}

function toggleNotificationGroupMember(index, checked) {
  const item = ngCandidateList[index];
  if (!item) return;
  const key = item._key || memberIdentityKey(item);
  if (!key) return;

  if (checked) ngSelectedMembers.set(key, { ...item, _key: key });
  else ngSelectedMembers.delete(key);
}

async function saveNotificationGroup() {
  const btn = document.getElementById('ngSaveBtn');
  btn.disabled = true;
  btn.textContent = 'Kaydediliyor…';

  const selectedMembers = Array.from(ngSelectedMembers.values());
  const internalUserIds = Array.from(
    new Set(
      selectedMembers
        .filter(m => Number.isInteger(m.id) && m.id > 0 && (m.auth_source || '').toLowerCase() !== 'ldap')
        .map(m => Number(m.id))
    )
  );
  const externalMembers = selectedMembers
    .filter(m => !(Number.isInteger(m.id) && m.id > 0 && (m.auth_source || '').toLowerCase() !== 'ldap'))
    .map(m => ({
      id: null,
      username: m.username || '',
      full_name: m.full_name || '',
      email: m.email || null,
      auth_source: 'ldap',
    }));

  const payload = {
    name: document.getElementById('ng_name').value.trim(),
    description: document.getElementById('ng_description').value.trim() || null,
    is_active: document.getElementById('ng_is_active').checked,
    user_ids: internalUserIds,
    members: externalMembers,
  };

  if (!payload.name) {
    showToast('Grup adı zorunludur', 'error');
    btn.disabled = false;
    btn.textContent = 'Kaydet';
    return;
  }

  if (payload.members.length === 0 && payload.user_ids.length === 0) {
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
    await loadNotificationGroups();
    renderNotificationGroupUserOptions();
  } catch (e) {
    showToast(e.message, 'error');
  }
});
