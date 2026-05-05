let profileData = null;
let editNameOpen = false;

function switchTab(tabId, btn) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(tabId)?.classList.add('active');
  btn?.classList.add('active');
}

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('tr-TR', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
}

function authSourceLabel(src) {
  const map = { local: 'Yerel (Kullanıcı Adı/Şifre)', ldap: 'LDAP / Active Directory', saml: 'SAML / Microsoft Entra ID' };
  return map[src] || src;
}

async function loadProfile() {
  try {
    profileData = await api('/api/profile');
  } catch (e) {
    showToast(e.message, 'error');
    return;
  }

  const p = profileData;
  const initial = (p.full_name || '?')[0].toUpperCase();

  // Header
  document.getElementById('avatarInitial').textContent = initial;
  document.getElementById('profileFullName').textContent = p.full_name;
  document.getElementById('profileSubtitle').textContent = `${authSourceLabel(p.auth_source)} · ${p.role === 'admin' ? 'Yönetici' : 'Salt Okunur'}`;

  // Hesap bilgileri
  document.getElementById('infoFullName').textContent     = p.full_name;
  document.getElementById('infoUsername').textContent     = p.username;
  document.getElementById('infoEmail').textContent        = p.email || '—';
  document.getElementById('infoAuthSource').textContent   = authSourceLabel(p.auth_source);
  document.getElementById('infoCreatedAt').textContent    = formatDate(p.created_at);
  document.getElementById('infoLastLogin').textContent    = formatDate(p.last_login);
  document.getElementById('infoRole').innerHTML = p.role === 'admin'
    ? '<span class="badge badge-blue">Yönetici</span>'
    : '<span class="badge badge-gray">Salt Okunur</span>';
  document.getElementById('infoActive').innerHTML = p.is_active
    ? '<span class="badge badge-green">Aktif</span>'
    : '<span class="badge badge-red">Pasif</span>';

  // Tercihler
  document.getElementById('prefDarkMode').checked  = !!p.preferences.dark_mode;
  document.getElementById('prefSidebar').checked   = !!p.preferences.sidebar_collapsed;

  // Güvenlik sekmesi
  document.getElementById('secAuthSource').textContent = authSourceLabel(p.auth_source);
  if (p.must_change_password) {
    document.getElementById('mustChangeRow').style.display = '';
  }
  if (p.auth_source !== 'local') {
    document.getElementById('passwordPanel').style.display = 'none';
  }

  // Oturum sekmesi
  document.getElementById('sessUsername').textContent    = p.username;
  document.getElementById('sessLastLogin').textContent   = formatDate(p.last_login);
  document.getElementById('sessAuthSource').textContent  = authSourceLabel(p.auth_source);

  // Ad güncelleme input
  document.getElementById('inputFullName').value = p.full_name;
}

function toggleEditName() {
  editNameOpen = !editNameOpen;
  document.getElementById('editNameForm').style.display = editNameOpen ? '' : 'none';
  if (editNameOpen) document.getElementById('inputFullName').focus();
}

async function saveFullName() {
  const name = document.getElementById('inputFullName').value.trim();
  if (!name) { showToast('Ad Soyad boş olamaz', 'error'); return; }
  try {
    await api('/api/profile/fullname', { method: 'PUT', body: JSON.stringify({ full_name: name }) });
    showToast('Ad Soyad güncellendi', 'success');
    toggleEditName();
    await loadProfile();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

function prefChanged() {
  document.getElementById('prefStatus').textContent = 'Değişiklikler kaydedilmedi';
}

async function savePreferences() {
  const dark    = document.getElementById('prefDarkMode').checked;
  const sidebar = document.getElementById('prefSidebar').checked;
  try {
    await api('/api/profile/preferences', { method: 'PUT', body: JSON.stringify({ dark_mode: dark, sidebar_collapsed: sidebar }) });
    document.getElementById('prefStatus').textContent = '';
    showToast('Tercihler kaydedildi', 'success');
    // Temayı anlık uygula
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    const shell = document.getElementById('appShell');
    if (shell) shell.classList.toggle('sidebar-collapsed', sidebar);
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function changePassword() {
  const current  = document.getElementById('currentPassword').value;
  const newPwd   = document.getElementById('newPassword').value;
  const confirm  = document.getElementById('confirmPassword').value;
  const errBox   = document.getElementById('passwordError');

  errBox.style.display = 'none';
  errBox.textContent   = '';

  if (!current) {
    errBox.textContent = 'Mevcut şifrenizi giriniz.';
    errBox.style.display = '';
    return;
  }
  if (newPwd.length < 8) {
    errBox.textContent = 'Yeni şifre en az 8 karakter olmalıdır.';
    errBox.style.display = '';
    return;
  }
  if (newPwd !== confirm) {
    errBox.textContent = 'Yeni şifreler eşleşmiyor.';
    errBox.style.display = '';
    return;
  }

  try {
    await api('/api/profile/password', { method: 'PUT', body: JSON.stringify({ current_password: current, new_password: newPwd }) });
    showToast('Şifre başarıyla güncellendi', 'success');
    document.getElementById('currentPassword').value = '';
    document.getElementById('newPassword').value     = '';
    document.getElementById('confirmPassword').value = '';
  } catch (e) {
    errBox.textContent   = e.message;
    errBox.style.display = '';
  }
}

document.addEventListener('DOMContentLoaded', loadProfile);
