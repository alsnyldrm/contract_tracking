/* ── Tab management ── */
function setupTabs() {
  document.querySelectorAll('#settingsTabs .tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#settingsTabs .tab-btn').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(x => x.classList.remove('active'));
      btn.classList.add('active');
      const panel = document.getElementById('tab-' + btn.dataset.tab);
      if (panel) panel.classList.add('active');
    });
  });
}

/* ── Load all settings ── */
async function fetchSettingsWithRetry() {
  try {
    return await api('/api/settings');
  } catch (e) {
    await new Promise(r => setTimeout(r, 800));
    return await api('/api/settings');
  }
}

async function loadSettings() {
  let data;
  try {
    data = await fetchSettingsWithRetry();
  } catch (e) {
    showToast('Ayarlar yüklenemedi: ' + e.message + ' (Mevcut değerler korunuyor)', 'error');
    return;
  }

  /* Timezone */
  const tzSel = document.getElementById('timezone');
  if (tzSel) tzSel.value = data.timezone || 'Europe/Istanbul';
  updateTzClock(data.timezone || 'Europe/Istanbul');

  /* LDAP */
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val ?? ''; };
  set('ldap_server_address',     data.ldap.server_address);
  set('ldap_port',               data.ldap.port || 636);
  set('ldap_base_dn',            data.ldap.base_dn);
  set('ldap_bind_dn',            data.ldap.bind_dn);
  set('ldap_bind_password',      data.ldap.bind_password || '');
  set('ldap_user_search_filter', data.ldap.user_search_filter);
  set('ldap_group_search_filter',data.ldap.group_search_filter);
  set('ldap_timeout_seconds',    data.ldap.timeout_seconds || 5);
  const chk = (id, val) => { const el = document.getElementById(id); if (el) el.checked = !!val; };
  chk('ldap_tls_enabled', data.ldap.tls_enabled);
  chk('ldap_verify_cert', data.ldap.verify_cert);

  /* SAML */
  chk('saml_enabled', data.saml.enabled);
  set('saml_entity_id',              data.saml.entity_id);
  set('saml_sso_url',                data.saml.sso_url);
  set('saml_slo_url',                data.saml.slo_url);
  set('saml_email_attribute',        data.saml.email_attribute);
  set('saml_display_name_attribute', data.saml.display_name_attribute);
  set('saml_nameid_mapping',         data.saml.nameid_mapping);
  set('saml_x509_certificate',       data.saml.x509_certificate || '');
  set('saml_attribute_mapping',      JSON.stringify(data.saml.attribute_mapping || {}, null, 2));
  set('saml_role_mapping',           JSON.stringify(data.saml.role_mapping || {}, null, 2));

  /* SMTP */
  set('smtp_host',         data.smtp.host);
  set('smtp_port',         data.smtp.port || 587);
  set('smtp_username',     data.smtp.username);
  set('smtp_password',     data.smtp.password || '');
  set('smtp_sender_email', data.smtp.sender_email);
  chk('smtp_tls_ssl',      data.smtp.tls_ssl);
  setSelectedSmtpAuthMode(data.smtp.auth_mode || 'auth');
  updateSmtpAuthModeUI();

  /* Log settings */
  set('log_max_file_size_mb',    data.log_settings.max_file_size_mb || 20);
  set('log_retention_days',      data.log_settings.retention_days || 30);
  set('log_auto_refresh_seconds',data.log_settings.auto_refresh_seconds || 5);
}

function updateTzClock(tz) {
  const el = document.getElementById('currentTzTime');
  if (!el) return;
  el.textContent = new Date().toLocaleString('tr-TR', { timeZone: tz });
}

/* ── SMTP mode UI ── */
function getSelectedSmtpAuthMode() {
  const el = document.querySelector('input[name="smtp_auth_mode"]:checked');
  return el?.value === 'relay' ? 'relay' : 'auth';
}

function setSelectedSmtpAuthMode(mode) {
  const auth = document.getElementById('smtp_auth_mode_auth');
  const relay = document.getElementById('smtp_auth_mode_relay');
  if (!auth || !relay) return;
  const selected = mode === 'relay' ? 'relay' : 'auth';
  auth.checked = selected === 'auth';
  relay.checked = selected === 'relay';
}

function updateSmtpAuthModeUI() {
  const isRelay = getSelectedSmtpAuthMode() === 'relay';
  const username = document.getElementById('smtp_username');
  const password = document.getElementById('smtp_password');
  const userField = document.getElementById('smtpUsernameField');
  const passField = document.getElementById('smtpPasswordField');
  const passHint = document.getElementById('smtpPasswordHint');

  if (username) username.disabled = isRelay;
  if (password) password.disabled = isRelay;
  if (userField) userField.style.opacity = isRelay ? '0.6' : '';
  if (passField) passField.style.opacity = isRelay ? '0.6' : '';
  if (passHint) {
    passHint.textContent = isRelay
      ? 'Relay modunda kullanıcı adı/şifre kullanılmaz'
      : 'Boş bırakılırsa mevcut şifre korunur';
  }
}

/* ── Timezone ── */
async function saveTimezone() {
  const tz = document.getElementById('timezone').value;
  try {
    await api('/api/settings/timezone', { method: 'PUT', body: JSON.stringify({ timezone: tz }) });
    showToast('Zaman dilimi kaydedildi', 'success');
    updateTzClock(tz);
  } catch (e) { showToast(e.message, 'error'); }
}

/* ── General ── */
async function saveGeneral() {
  showToast('Genel ayarlar kaydedildi', 'success');
}

/* ── LDAP ── */
async function saveLdap() {
  const payload = {
    server_address:      document.getElementById('ldap_server_address').value.trim(),
    port:                Number(document.getElementById('ldap_port').value) || 636,
    base_dn:             document.getElementById('ldap_base_dn').value.trim(),
    bind_dn:             document.getElementById('ldap_bind_dn').value.trim(),
    bind_password:       document.getElementById('ldap_bind_password').value,
    user_search_filter:  document.getElementById('ldap_user_search_filter').value.trim(),
    group_search_filter: document.getElementById('ldap_group_search_filter').value.trim(),
    timeout_seconds:     Number(document.getElementById('ldap_timeout_seconds').value) || 5,
    tls_enabled:         document.getElementById('ldap_tls_enabled').checked,
    verify_cert:         document.getElementById('ldap_verify_cert').checked,
  };
  try {
    await api('/api/settings/ldap', { method: 'PUT', body: JSON.stringify(payload) });
    showToast('LDAPS ayarları kaydedildi', 'success');
    document.getElementById('ldap_bind_password').value = '••••••••';
  } catch (e) { showToast(e.message, 'error'); }
}

async function testLdap() {
  const btn = event.target;
  const resultEl = document.getElementById('ldapTestResult');
  btn.disabled = true; btn.textContent = '🔄 Test ediliyor…';
  try {
    const data = await api('/api/settings/ldap/test', { method: 'POST', body: JSON.stringify({}) });
    resultEl.className = data.ok ? 'alert alert-success' : 'alert alert-error';
    resultEl.innerHTML = `<span>${data.ok ? '✓' : '✕'}</span><span>${escHtml(data.message)}</span>`;
    resultEl.style.display = '';
  } catch (e) {
    resultEl.className = 'alert alert-error';
    resultEl.innerHTML = `<span>✕</span><span>${escHtml(e.message)}</span>`;
    resultEl.style.display = '';
  } finally {
    btn.disabled = false; btn.textContent = '🔌 Bağlantıyı Test Et';
  }
}

/* ── SAML ── */
async function saveSaml() {
  let attrMapping = {}, roleMapping = {};
  try { attrMapping = JSON.parse(document.getElementById('saml_attribute_mapping').value || '{}'); } catch { attrMapping = {}; }
  try { roleMapping = JSON.parse(document.getElementById('saml_role_mapping').value || '{}');       } catch { roleMapping = {}; }

  const payload = {
    enabled:                 document.getElementById('saml_enabled').checked,
    entity_id:               document.getElementById('saml_entity_id').value.trim(),
    sso_url:                 document.getElementById('saml_sso_url').value.trim(),
    slo_url:                 document.getElementById('saml_slo_url').value.trim(),
    email_attribute:         document.getElementById('saml_email_attribute').value.trim(),
    display_name_attribute:  document.getElementById('saml_display_name_attribute').value.trim(),
    nameid_mapping:          document.getElementById('saml_nameid_mapping').value.trim(),
    x509_certificate:        document.getElementById('saml_x509_certificate').value.trim(),
    attribute_mapping:       attrMapping,
    role_mapping:            roleMapping,
  };
  try {
    await api('/api/settings/saml', { method: 'PUT', body: JSON.stringify(payload) });
    showToast('SAML ayarları kaydedildi', 'success');
  } catch (e) { showToast(e.message, 'error'); }
}

/* ── SMTP ── */
async function saveSmtp() {
  const authMode = getSelectedSmtpAuthMode();
  const username = document.getElementById('smtp_username').value.trim();
  const password = document.getElementById('smtp_password').value;

  if (authMode === 'auth' && !username) {
    showToast('Kimlik doğrulama modunda kullanıcı adı zorunludur', 'warn');
    return;
  }

  const payload = {
    host:         document.getElementById('smtp_host').value.trim(),
    port:         Number(document.getElementById('smtp_port').value) || 587,
    auth_mode:    authMode,
    username:     authMode === 'relay' ? '' : username,
    password:     authMode === 'relay' ? '' : password,
    sender_email: document.getElementById('smtp_sender_email').value.trim(),
    tls_ssl:      document.getElementById('smtp_tls_ssl').checked,
  };
  try {
    await api('/api/settings/smtp', { method: 'PUT', body: JSON.stringify(payload) });
    showToast('SMTP ayarları kaydedildi', 'success');
    document.getElementById('smtp_password').value = authMode === 'auth' ? '••••••••' : '';
    updateSmtpAuthModeUI();
  } catch (e) { showToast(e.message, 'error'); }
}

async function testSmtp() {
  const btn = event.target;
  const resultEl = document.getElementById('smtpResult');
  btn.disabled = true; btn.textContent = '🔄 Gönderiliyor…';
  try {
    const result = await api('/api/settings/smtp/test', { method: 'POST', body: JSON.stringify({}) });
    resultEl.className = result.ok ? 'alert alert-success' : 'alert alert-error';
    resultEl.innerHTML = `<span>${result.ok ? '✓' : '✕'}</span><span>${escHtml(result.message)}</span>`;
    resultEl.style.display = '';
  } catch (e) {
    resultEl.className = 'alert alert-error';
    resultEl.innerHTML = `<span>✕</span><span>${escHtml(e.message)}</span>`;
    resultEl.style.display = '';
  } finally {
    btn.disabled = false; btn.textContent = '📧 Test Mail Gönder';
  }
}

/* ── Report modules ── */
async function loadReportModulesSettings() {
  try {
    const rows = await api('/api/reports/modules');
    const tbody = document.getElementById('reportModulesSettingsTbody');
    if (!tbody) return;
    tbody.innerHTML = rows.map(m => `
      <tr>
        <td style="font-weight:500">${escHtml(m.name)}</td>
        <td><code style="font-size:11.5px;background:var(--bg);padding:2px 6px;border-radius:4px">${escHtml(m.code)}</code></td>
        <td>${m.is_active ? '<span class="badge badge-green">Aktif</span>' : '<span class="badge badge-gray">Pasif</span>'}</td>
        <td>
          <button class="btn btn-sm ${m.is_active ? 'btn-danger' : 'btn-success'}"
                  onclick="toggleReportModule(${m.id}, ${!m.is_active})">
            ${m.is_active ? 'Pasifleştir' : 'Aktifleştir'}
          </button>
        </td>
      </tr>`).join('');
  } catch (e) { showToast(e.message, 'error'); }
}

async function toggleReportModule(id, isActive) {
  try {
    await api(`/api/reports/modules/${id}`, { method: 'PUT', body: JSON.stringify({ is_active: isActive }) });
    showToast(isActive ? 'Modül aktifleştirildi' : 'Modül pasifleştirildi', 'success');
    loadReportModulesSettings();
  } catch (e) { showToast(e.message, 'error'); }
}

/* ── Log settings ── */
async function saveLogSettings() {
  const payload = {
    max_file_size_mb:     Number(document.getElementById('log_max_file_size_mb').value) || 20,
    retention_days:       Number(document.getElementById('log_retention_days').value) || 30,
    auto_refresh_seconds: Number(document.getElementById('log_auto_refresh_seconds').value) || 5,
  };
  try {
    await api('/api/settings/logs', { method: 'PUT', body: JSON.stringify(payload) });
    showToast('Log ayarları kaydedildi', 'success');
  } catch (e) { showToast(e.message, 'error'); }
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
  setupTabs();
  loadSettings();
  loadReportModulesSettings();

  document.querySelectorAll('input[name="smtp_auth_mode"]').forEach(el => {
    el.addEventListener('change', updateSmtpAuthModeUI);
  });

  /* Timezone clock updater */
  setInterval(() => {
    const tz = document.getElementById('timezone')?.value || 'Europe/Istanbul';
    updateTzClock(tz);
  }, 5000);

  document.getElementById('timezone')?.addEventListener('change', e => updateTzClock(e.target.value));
});
