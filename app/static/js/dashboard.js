let statusChartInstance = null;

function showDashboardError(msg) {
  const grid = document.getElementById('widgetGrid');
  if (grid) grid.innerHTML = `<div class="alert alert-error" style="grid-column:1/-1">${msg}</div>`;
}

async function loadDashboard() {
  let data;
  try {
    data = await api('/api/dashboard/summary');
  } catch (e) {
    showDashboardError(e.message);
    return;
  }

  const labels = {
    toplam_kurum:     'Toplam Kurum',
    toplam_sozlesme:  'Toplam Sözleşme',
    aktif_sozlesme:   'Aktif Sözleşme',
    suresi_dolmus:    'Süresi Dolmuş',
    bitecek_30:       '30 Günde Bitiyor',
    bitecek_60:       '60 Günde Bitiyor',
    bitecek_90:       '90 Günde Bitiyor',
    kritik_sozlesme:  'Kritik Seviye',
    toplam_tutar:     'Toplam Tutar (₺)',
    aylik_yenilenecek:'Aylık Yenilenecek',
  };

  const grid = document.getElementById('widgetGrid');
  if (grid) {
    grid.innerHTML = '';
    Object.entries(data.widgets).forEach(([k, v]) => {
      const card = document.createElement('div');
      card.className = 'widget';
      const display = typeof v === 'number' ? v.toLocaleString('tr-TR') : v;
      card.innerHTML = `<div class="label">${labels[k] || k}</div><div class="value">${display}</div>`;
      grid.appendChild(card);
    });
  }

  const tbody = document.querySelector('#nearestTable tbody');
  if (tbody) {
    if (data.nearest_contracts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--muted)">Yaklaşan sözleşme yok</td></tr>';
    } else {
      tbody.innerHTML = data.nearest_contracts.map(r =>
        `<tr>
          <td><a href="/contracts">${r.contract_name}</a></td>
          <td>${r.end_date || '—'}</td>
          <td>${r.status}</td>
        </tr>`
      ).join('');
    }
  }

  const ctx = document.getElementById('statusChart');
  if (ctx) {
    if (statusChartInstance) {
      statusChartInstance.destroy();
      statusChartInstance = null;
    }
    if (data.status_chart.length > 0) {
      statusChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: data.status_chart.map(x => x.status),
          datasets: [{
            label: 'Sözleşme Sayısı',
            data: data.status_chart.map(x => x.count),
            backgroundColor: '#2f669f',
            borderRadius: 6,
          }],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
        },
      });
    } else {
      ctx.parentElement.innerHTML += '<p style="color:var(--muted);text-align:center;font-size:13px">Henüz sözleşme yok</p>';
    }
  }
}

document.addEventListener('DOMContentLoaded', loadDashboard);
