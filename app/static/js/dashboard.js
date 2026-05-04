async function loadDashboard() {
  const data = await api('/api/dashboard/summary');
  const labels = {
    toplam_kurum: 'Toplam kurum',
    toplam_sozlesme: 'Toplam sözleşme',
    aktif_sozlesme: 'Aktif sözleşme',
    suresi_dolmus: 'Süresi dolmuş',
    bitecek_30: '30 gün içinde bitecek',
    bitecek_60: '60 gün içinde bitecek',
    bitecek_90: '90 gün içinde bitecek',
    kritik_sozlesme: 'Kritik seviye',
    toplam_tutar: 'Toplam tutar',
    aylik_yenilenecek: 'Aylık yenilenecek'
  };
  const grid = document.getElementById('widgetGrid');
  grid.innerHTML = '';
  Object.entries(data.widgets).forEach(([k, v]) => {
    const card = document.createElement('div');
    card.className = 'widget';
    card.innerHTML = `<div>${labels[k] || k}</div><div class="value">${typeof v === 'number' ? v.toLocaleString('tr-TR') : v}</div>`;
    grid.appendChild(card);
  });

  const tbody = document.querySelector('#nearestTable tbody');
  tbody.innerHTML = data.nearest_contracts.map(r => `<tr><td>${r.contract_name}</td><td>${r.end_date || ''}</td><td>${r.status}</td></tr>`).join('');

  const ctx = document.getElementById('statusChart');
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.status_chart.map(x => x.status),
      datasets: [{ label: 'Sözleşme Sayısı', data: data.status_chart.map(x => x.count), backgroundColor: '#2f669f' }]
    },
    options: { responsive: true, plugins: { legend: { display: false } } }
  });
}
document.addEventListener('DOMContentLoaded', () => loadDashboard().catch(e => alert(e.message)));
