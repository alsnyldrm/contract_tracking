let profileData = null;

async function loadProfile() {
  profileData = await api('/api/profile');
  document.getElementById('profileBox').innerHTML = `
    <h3>${profileData.full_name}</h3>
    <p>Kullanıcı adı: ${profileData.username}</p>
    <p>E-posta: ${profileData.email || '-'}</p>
    <p>Rol: ${profileData.role}</p>
    <p>Kimlik kaynağı: ${profileData.auth_source}</p>
    ${profileData.must_change_password ? '<p style="color:#b42318;">İlk giriş sonrası şifre değişikliği zorunludur.</p>' : ''}
  `;
  document.getElementById('prefDarkMode').checked = !!profileData.preferences.dark_mode;
  document.getElementById('prefSidebar').checked = !!profileData.preferences.sidebar_collapsed;
  if (profileData.auth_source !== 'local') {
    document.getElementById('passwordPanel').style.display = 'none';
  }
}

async function savePreferences() {
  await api('/api/profile/preferences', { method: 'PUT', body: JSON.stringify({ dark_mode: document.getElementById('prefDarkMode').checked, sidebar_collapsed: document.getElementById('prefSidebar').checked }) });
  location.reload();
}

async function changePassword() {
  const newPassword = document.getElementById('newPassword').value;
  await api('/api/profile/password', { method: 'PUT', body: JSON.stringify({ new_password: newPassword }) });
  alert('Şifre güncellendi');
  document.getElementById('newPassword').value = '';
}

document.addEventListener('DOMContentLoaded', () => loadProfile().catch(e => alert(e.message)));
