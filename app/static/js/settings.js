function setupTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(x => x.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    });
  });
}

async function loadSettings() {
  const data = await api('/api/settings');
  document.getElementById('timezone').value = data.timezone;

  document.getElementById('ldap_server_address').value   = data.ldap.server_address || '';
  document.getElementById('ldap_port').value             = data.ldap.port || 636;
  document.getElementById('ldap_base_dn').value          = data.ldap.base_dn || '';
  document.getElementById('ldap_bind_dn').value          = data.ldap.bind_dn || '';
  document.getElementById('ldap_bind_password').value    = data.ldap.bind_password || '';
  document.getElementById('ldap_user_search_filter').value  = data.ldap.user_search_filter || '';
  document.getElementById('ldap_group_search_filter').value = data.ldap.group_search_filter || '';
  document.getElementById('ldap_timeout_seconds').value  = data.ldap.timeout_seconds || 5;
  document.getElementById('ldap_tls_enabled').checked    = !!data.ldap.tls_enabled;
  document.getElementById('ldap_verify_cert').checked    = !!data.ldap.verify_cert;

  document.getElementById('saml_enabled').checked              = !!data.saml.enabled;
  document.getElementById('saml_entity_id').value              = data.saml.entity_id || '';
  document.getElementById('saml_sso_url').value                = data.saml.sso_url || '';
  document.getElementById('saml_slo_url').value                = data.saml.slo_url || '';
  document.getElementById('saml_email_attribute').value        = data.saml.email_attribute || '';
  document.getElementById('saml_display_name_attribute').value = data.saml.display_name_attribute || '';
  document.getElementById('saml_nameid_mapping').value         = data.saml.nameid_mapping || '';
  document.getElementById('saml_x509_certificate').value       = data.saml.x509_certificate || '';
  document.getElementById('saml_attribute_mapping').value      = JSON.stringify(data.saml.attribute_mapping || {});
  document.getElementById('saml_role_mapping').value           = JSON.stringify(data.saml.role_mapping || {});

  document.getElementById('smtp_host').value         = data.smtp.host || '';
  document.getElementById('smtp_port').value         = data.smtp.port || 587;
  document.getElementById('smtp_username').value     = data.smtp.username || '';
  document.getElementById('smtp_password').value     = data.smtp.password || '';
  document.getElementById('smtp_sender_email').value = data.smtp.sender_email || '';
  document.getElementById('smtp_tls_ssl').checked    = !!data.smtp.tls_ssl;

  document.getElementById('log_max_file_size_mb').value    = data.log_settings.max_file_size_mb || 20;
  document.getElementById('log_retention_days').value      = data.log_settings.retention_days || 30;
  document.getElementById('log_auto_refresh_seconds').value = data.log_settings.auto_refresh_seconds || 5;
}

async function saveTimezone() {
  try {
    await api('/api/settings/timezone', { method: 'PUT', body: JSON.stringify({ timezone: document.getElementById('timezone').value }) });
    showToast('Timezone kaydedildi', 'success');
  } catch (e) { showToast(e.message, 'error'); }
}

async function saveLdap() {
  const payload = {
    server_address: document.getElementById('ldap_server_address').value,
    port: Number(document.getElementById('ldap_port').value),
    base_dn: document.getElementById('ldap_base_dn').value,
    bind_dn: document.getElementById('ldap_bind_dn').value,
    bind_password: document.getElementById('ldap_bind_password').value,
    user_search_filter: document.getElementById('ldap_user_search_filter').value,
    group_search_filter: document.getElementById('ldap_group_search_filter').value,
    timeout_seconds: Number(document.getElementById('ldap_timeout_seconds').value),
    tls_enabled: document.getElementById('ldap_tls_enabled').checked,
    verify_cert: document.getElementById('ldap_verify_cert').checked,
  };
  try {
    await api('/api/settings/ldap', { method: 'PUT', body: JSON.stringify(payload) });
    showToast('LDAPS ayarları kaydedildi', 'success');
  } catch (e) { showToast(e.message, 'error'); }
}

async function testLdap() {
  try {
    const data = await api('/api/settings/ldap/test', { method: 'POST', body: JSON.stringify({}) });
    const el = document.getElementById('ldapTestResult');
    el.textContent = data.message;
    el.className = data.ok ? 'alert alert-success' : 'alert alert-error';
    el.style.display = '';
  } catch (e) { showToast(e.message, 'error'); }
}

async function saveSaml() {
  const payload = {
    enabled: document.getElementById('saml_enabled').checked,
    entity_id: document.getElementById('saml_entity_id').value,
    sso_url: document.getElementById('saml_sso_url').value,
    slo_url: document.getElementById('saml_slo_url').value,
    email_attribute: document.getElementById('saml_email_attribute').value,
    display_name_attribute: document.getElementById('saml_display_name_attribute').value,
    nameid_mapping: document.getElementById('saml_nameid_mapping').value,
    x509_certificate: document.getElementById('saml_x509_certificate').value,
    attribute_mapping: document.getElementById('saml_attribute_mapping').value,
    role_mapping: document.getElementById('saml_role_mapping').value,
  };
  try {
    await api('/api/settings/saml', { method: 'PUT', body: JSON.stringify(payload) });
    showToast('SAML ayarları kaydedildi', 'success');
  } catch (e) { showToast(e.message, 'error'); }
}

async function saveSmtp() {
  const payload = {
    host: document.getElementById('smtp_host').value,
    port: Number(document.getElementById('smtp_port').value),
    username: document.getElementById('smtp_username').value,
    password: document.getElementById('smtp_password').value,
    sender_email: document.getElementById('smtp_sender_email').value,
    tls_ssl: document.getElementById('smtp_tls_ssl').checked,
  };
  try {
    await api('/api/settings/smtp', { method: 'PUT', body: JSON.stringify(payload) });
    showToast('SMTP ayarları kaydedildi', 'success');
  } catch (e) { showToast(e.message, 'error'); }
}

async function testSmtp() {
  try {
    const result = await api('/api/settings/smtp/test', { method: 'POST', body: JSON.stringify({}) });
    const el = document.getElementById('smtpResult');
    el.textContent = result.message;
    el.className = result.ok ? 'alert alert-success' : 'alert alert-error';
    el.style.display = '';
  } catch (e) { showToast(e.message, 'error'); }
}

async function saveLogSettings() {
  const payload = {
    max_file_size_mb: Number(document.getElementById('log_max_file_size_mb').value),
    retention_days: Number(document.getElementById('log_retention_days').value),
    auto_refresh_seconds: Number(document.getElementById('log_auto_refresh_seconds').value),
  };
  try {
    await api('/api/settings/logs', { method: 'PUT', body: JSON.stringify(payload) });
    showToast('Log ayarları kaydedildi', 'success');
  } catch (e) { showToast(e.message, 'error'); }
}

document.addEventListener('DOMContentLoaded', () => {
  setupTabs();
  loadSettings().catch(e => showToast(e.message, 'error'));
});
