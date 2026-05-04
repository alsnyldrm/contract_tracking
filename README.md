# Contract Tracking

Contract Tracking, kurum sözleşmelerinin merkezi takibi için hazırlanmış, Docker üzerinde çalışan, PostgreSQL kullanan, Türkçe ve kurumsal arayüzlü bir web uygulamasıdır.

## Özellikler
- Dashboard (15+ widget, grafikler, yaklaşan bitişler)
- Kurum yönetimi
- Sözleşme yönetimi (soft delete, etiket, kritik seviye, durum)
- Belge yönetimi (PDF/DOC/DOCX/XLS/XLSX/PNG/JPG/JPEG)
- Rapor modülü (PDF/CSV UTF-8 BOM/Excel export)
- Kullanıcı ve rol yönetimi (`admin`, `readonly`)
- Profil + DB tabanlı kullanıcı tercihleri (dark mode, sidebar)
- Ayarlar:
  - Genel
  - Time Zone
  - LDAPS
  - SAML
  - SMTP/Bildirim
  - Raporlar
  - Log Ayarları
- Log Yönetimi ekranı (tip/limit/seviye/arama/indir/csv export)
- Full log mimarisi (kategori bazlı ayrı dosyalar)
- Audit log hem DB hem dosya
- Güvenli oturum, CSRF header kontrolü, rate limit, parola hashleme
- Uygulama içi scheduler (cron yok)

## Mimari
- Backend: FastAPI + SQLAlchemy + Alembic
- Frontend: Jinja template + Vanilla JS + Chart.js
- Veritabanı: Harici PostgreSQL
- Container: Tek uygulama container’ı (Nginx/Apache yok)

## Proje Yapısı
- `app/` uygulama kodu
- `app/routers/` API ve sayfa rotaları
- `app/services/` iş kuralları
- `app/templates/` HTML şablonlar
- `app/static/` CSS/JS/logo/favicon
- `alembic/` migration
- `scripts/run_migrations.py` migration çalıştırma
- `scripts/seed.py` seed çalıştırma

## Kurulum
1. Repo klonlayın:
```bash
git clone <repo_url>
cd contract_tracking
```
2. `.env` oluşturun:
```bash
cp .env.example .env
```
3. `.env` içine gerçek değerleri girin (`DB_PASSWORD`, `SECRET_KEY`).
4. Build:
```bash
docker compose build
```
5. Ayağa kaldırın:
```bash
docker compose up -d
```

## Migration / Seed
Container çalıştıktan sonra:
```bash
docker compose exec contract-tracking python scripts/run_migrations.py
docker compose exec contract-tracking python scripts/seed.py
```

## Varsayılan Kullanıcı
- Kullanıcı adı: `admin`
- Şifre: `Aa123456`
- İlk girişte şifre değiştirme uyarısı vardır.

## .env Ayarları
Örnek dosya: `.env.example`
- DB host: `10.2.0.31`
- DB adı: `ctracking`
- DB kullanıcı: `ctracking`
- Şifreyi `.env` içinde tanımlayın.

## Docker
- Port mapping: `8087:80`
- Container içi uygulama portu: `80`
- PostgreSQL compose içinde yok (harici DB)
- Volume:
  - `uploaded_contract_documents:/app/data/documents`
  - `logs:/app/logs`

## LDAPS Ayarı
1. `Ayarlar > LDAPS` sekmesine girin.
2. Sunucu, port, base DN, bind DN, bind password, filtreleri girin.
3. `Test Bağlantısı` ile doğrulayın.
4. Sonuçlar `logs/ldap.log` dosyasına yazılır.

## SAML Ayarı (Microsoft Entra ID / SAML)
1. `Ayarlar > SAML` sekmesinden SAML’i aktif edin.
2. `Entity ID`, `SSO URL`, `SLO URL`, `X.509 certificate` girin.
3. Attribute mapping, NameID, email/display name mapping alanlarını kaydedin.
4. Login ekranındaki “Microsoft Entra ID ile Giriş” butonunu kullanın.
5. SAML ile gelen kullanıcılar varsayılan `readonly` oluşturulur.

## SMTP / Bildirim
- `Ayarlar > SMTP / Bildirim` sekmesinden SMTP bilgilerini girin.
- `Test Mail` ile bağlantıyı doğrulayın.
- Kayıtlar `logs/notification.log` dosyasına yazılır.

## Log Dosyaları
- `logs/app.log`
- `logs/error.log`
- `logs/auth.log`
- `logs/saml.log`
- `logs/ldap.log`
- `logs/db.log`
- `logs/audit.log`
- `logs/document.log`
- `logs/report.log`
- `logs/security.log`
- `logs/api.log`
- `logs/scheduler.log`
- `logs/notification.log`
- `logs/profile.log`
- `logs/settings.log`

Her kayıt JSON satır formatında tutulur. Hassas veriler maskeleme filtresinden geçer.

## Log Yönetimi
- Sadece admin erişebilir.
- Tip, seviye, kullanıcı, IP ve metin filtresi desteklenir.
- Son 100/500/1000 satır okunur.
- Log dosyası indirilebilir / CSV export alınabilir.

## Log Rotation
- RotatingFileHandler aktif.
- Dosya boyutu ve saklama günleri `Log Ayarları` ve `.env` ile yönetilir.

## Raporlama
- Hazır 10 rapor modülü seed ile gelir.
- Modüller admin tarafından aktif/pasif yapılabilir.
- Export formatları: PDF, CSV (UTF-8 BOM), XLSX.

## Dosya Yükleme Dizini
- Container içinde: `/app/data/documents`
- Docker volume: `uploaded_contract_documents`

## Backup Önerisi
- PostgreSQL için düzenli `pg_dump` alın.
- `logs` ve `uploaded_contract_documents` volumelerini yedekleyin.

## Güvenlik Notları
- DB bilgileri kodda değil, `.env` üzerinden okunur.
- Şifreler hash’li tutulur.
- Session cookie + server side session tablosu kullanılır.
- CSRF koruması (`X-CSRF-Token`) aktiftir.
- Brute force/rate limit login akışında uygulanır.
- Hassas alanlar loglarda maskelenir.

## Nginx Reverse Proxy Örneği (Host Tarafı)
```nginx
server {
    listen 80;
    server_name contract.example.com;

    location / {
        proxy_pass http://127.0.0.1:8087;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Kullanılan Varsayılan Sayfalar
- Login ekranı: `sample.html` tasarım yaklaşımı Contract Tracking içeriğine uyarlanmıştır.
- Uygulama favicon: `app/static/img/favicon.svg`
- Uygulama logo: `app/static/img/logo.svg`
