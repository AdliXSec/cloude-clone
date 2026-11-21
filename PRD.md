# Product Requirements Document (PRD)
# KosanHub — Aplikasi Manajemen Kos-Kosan

**Versi**: 1.0  
**Status**: MVP (Minimum Viable Product)  
**Tanggal**: 2026-11-19  
**Tim**: Naufal Syahruradli (backend), Noval (container), Gusti Prabu (Jenkins), Haydar (QA)

---

## 1. Overview

KosanHub adalah aplikasi web untuk mengelola properti kos-kosan: data properti, kamar, penyewa, kontrak sewa, tagihan bulanan, dan pencatatan pembayaran. Sistem otomatis menghitung denda keterlambatan pembayaran dan mendeteksi tunggakan.

**Tujuan Utama:**
- Menyederhanakan pencatatan kontrak sewa dan tagihan
- Otomasi perhitungan denda dan tunggakan
- Dashboard untuk monitoring kolektabilitas
- API untuk integrasi dengan sistem eksternal (Jenkins, QA tools)

---

## 2. User Personas

### 2.1 Admin / Operator Kos
- **Peran**: Mengelola properti, kamar, penyewa, kontrak, tagihan, pembayaran, dan pengguna sistem.
- **Akses**: Dashboard, semua halaman CRUD form, halaman pembayaran, API POST/PUT/DELETE.
- **Kebutuhan**:
  - Tambah/edit/hapus properti dan kamar
  - Input penyewa baru dan data kontraknya
  - Generate tagihan bulanan (batch)
  - Catat pembayaran masuk
  - Monitor tunggakan dan riwayat pembayaran
  - Kelola akun user lain di sistem

### 2.2 Aplikasi Eksternal (Jenkins, QA)
- **Peran**: Automation testing dan CI/CD pipeline.
- **Akses**: API `/api/*` via HTTP Basic auth (email:password).
- **Kebutuhan**:
  - Baca daftar properti, kamar, penyewa, kontrak, tagihan, pembayaran
  - Buat/update properti, kamar, penyewa, kontrak via API
  - Generate dan monitor billing job
  - Verifikasi aturan bisnis (1 kamar 1 kontrak aktif, denda benar, dll)

---

## 3. User Flows & Pages

### 3.1 Web Pages (Flask Jinja Template)

| Halaman | URL | Akses | Deskripsi |
|---------|-----|-------|-----------|
| Login | `/login` | Publik | Form login (email + password). Redirect ke dashboard jika sudah login. |
| Dashboard | `/` | Wajib login | Overview: jumlah properti, kamar, penyewa, kontrak aktif, tagihan belum dibayar. |
| Properti | `/properties` | Wajib login | List properti. Admin: tombol Tambah/Edit/Hapus. |
| Kamar | `/rooms` | Wajib login | List kamar (per properti). Admin: tombol Tambah/Edit/Hapus. |
| Penyewa | `/tenants` | Wajib login | List penyewa & kamar aktif per penyewa. Admin: tombol Tambah/Edit/Hapus. |
| Kontrak | `/contracts` | Wajib login | List kontrak aktif & history. Admin: tombol Tambah/Akhiri (soft delete). |
| Tagihan | `/bills` | Wajib login | List tagihan. Admin: tombol Bayar (catat pembayaran). Plus tombol "Generate Tagihan Bulan Ini". |
| Pembayaran | `/payments` | Wajib login | Riwayat pembayaran. Read-only. |
| Tunggakan | `/arrears` | Wajib login | List kontrak dengan tunggakan > 0. Computed field dari snapshot tagihan. |
| Job | `/jobs` | Wajib login | List billing job, status (PENDING/PROCESSING/COMPLETED/FAILED), jumlah tagihan dibuat. |
| Admin > Properti Form | `/admin/properties/new`, `/admin/properties/<id>/edit` | Admin-only | Form input nama & alamat properti. |
| Admin > Kamar Form | `/admin/rooms/new`, `/admin/rooms/<id>/edit` | Admin-only | Form input properti, nomor, harga. |
| Admin > Penyewa Form | `/admin/tenants/new`, `/admin/tenants/<id>/edit` | Admin-only | Form input nama, telepon, email. |
| Admin > Kontrak Form | `/admin/contracts/new` | Admin-only | Form pilih kamar, penyewa, tanggal mulai, harga. Validasi: 1 kamar max 1 ACTIVE kontrak. |
| Admin > Akhiri Kontrak | `/admin/contracts/<id>/end` (POST) | Admin-only | Soft delete (set status=ENDED). |
| Admin > Bayar Tagihan | `/admin/bills/<id>/pay` | Admin-only | Form input nominal, tanggal bayar, metode (default TRANSFER). |
| Admin > Generate Tagihan | `/admin/jobs/generate` (POST) | Admin-only | Enqueue billing job. User input tahun & bulan (default bulan sekarang). |
| Admin > Profile | `/admin/profile` | Wajib login | Form ganti password (old + new + confirm). Clear sesi setelah sukses. |
| Admin > Kelola User | `/admin/users` | Admin-only | List user. Tombol Hapus (tidak bisa hapus akun sendiri). Link "Tambah User". |
| Admin > Tambah User | `/admin/users/new` | Admin-only | Form email (lowercase) & password (min 8 char). Email unik. User baru langsung bisa login. |
| Health | `/health` | Publik | Endpoint simple untuk healthcheck Docker. Response 200: `{"status":"ok","database":"connected"}`; 503 jika DB tidak terhubung. |

**Catatan Menu Navigasi:**
```
KosanHub
  Dashboard
  Properti
  Kamar
  Penyewa
  Kontrak
  Tagihan
  Pembayaran
  Tunggakan
  Job
  User (muncul di nav, diarahkan ke login jika anon)
  
Topbar (kanan):
  [Email User] ← link ke Profile
  Logout (form POST)
```

### 3.2 Admin CRUD Forms

**Template Umum (`form.html`):**
```
Judul: "[Tambah|Edit] [Entitas]"
Field: input text/select/number (sesuai model)
Tombol: Simpan (POST) | Batal (kembali ke list)
Validasi: client-side (required, min/max length)
Server-side: clean_str(), validate unik, check FK, error flash
```

**Masing-masing Form:**

1. **Tambah/Edit Properti**
   - Nama (text, required, max 120 char)
   - Alamat (text, required, max 255 char)
   
2. **Tambah/Edit Kamar**
   - Properti (select, required)
   - Nomor (text, required, max 20 char) — unik per properti
   - Harga/Bulan (number, required, min 1)

3. **Tambah/Edit Penyewa**
   - Nama (text, required, max 120 char)
   - Telepon (text, required; 8-15 digit angka, boleh diawali +; spasi dan - dibuang)
   - Email (email, optional, max 120 char)

4. **Tambah Kontrak**
   - Kamar (select, required)
   - Penyewa (select, required)
   - Tanggal Mulai (date, required)
   - Harga/Bulan (number, required, min 1; default: harga kamar)
   - Validasi: Kamar tidak boleh punya ACTIVE kontrak lain

5. **Catat Pembayaran**
   - Bill ID (auto, hidden)
   - Nominal (number, required, min 1; default terisi sisa tagihan; server menolak jika melebihi sisa)
   - Tanggal Bayar (date, required; default: hari ini)
   - Metode (teks bebas max 30 char, default TRANSFER; backend belum membatasi daftar pilihan)
   - Display: tenant, kamar, periode, jumlah tagihan original, outstanding hari ini

6. **Tambah User**
   - Email (email, required, max 120 char, lowercase, unik)
   - Password (password, required, min 8 char)

7. **Profile > Ubah Password**
   - Password Lama (password, required)
   - Password Baru (password, required, min 8 char)
   - Ulangi Password (password, required, sama dengan password baru)
   - Action: validate password lama, bersihkan sesi, arahkan ke login

---

## 4. API Specification

**Base Path:** `/api/`  
**Auth:** GET = terbuka, POST/PUT/DELETE = HTTP Basic (`curl -u email:password`)  
**Response:** JSON, status code 200/201/400/401/404/409

### 4.1 Properties

```
GET    /api/properties                 → list semua properti
POST   /api/properties                 → create (admin-only)
GET    /api/properties/<id>            → get detail
PUT    /api/properties/<id>            → update (admin-only)
DELETE /api/properties/<id>            → delete (admin-only, check FK)
```

### 4.2 Rooms

```
GET    /api/rooms                      → list semua kamar
POST   /api/rooms                      → create (admin-only)
GET    /api/rooms/<id>                 → get detail
PUT    /api/rooms/<id>                 → update (admin-only)
DELETE /api/rooms/<id>                 → delete (admin-only, check FK)
```

### 4.3 Tenants

```
GET    /api/tenants                    → list semua penyewa
POST   /api/tenants                    → create (admin-only)
GET    /api/tenants/<id>               → get detail + list kamar aktif
PUT    /api/tenants/<id>               → update (admin-only)
DELETE /api/tenants/<id>               → delete (admin-only, check FK)
```

### 4.4 Contracts

```
GET    /api/contracts                  → list kontrak (aktif + history)
POST   /api/contracts                  → create (admin-only)
GET    /api/contracts/<id>             → get detail
POST   /api/contracts/<id>/end         → soft delete, set status=ENDED (admin-only)
```

### 4.5 Bills

```
GET    /api/bills                      → list tagihan
POST   /api/bills                      → create (admin-only, via job worker biasanya)
GET    /api/bills/<id>                 → get detail + outstanding snapshot
GET    /api/bills/arrears              → list tagihan dengan unpaid & overdue
```

### 4.6 Payments

```
GET    /api/payments                   → list pembayaran
POST   /api/payments                   → create (admin-only)
```

### 4.7 Billing Jobs

```
GET    /api/jobs                       → list job (semua status)
POST   /api/jobs/generate-bills        → enqueue job (admin-only)
GET    /api/jobs/<id>                  → get detail
```

**Job Request Body:**
```json
{
  "year": 2026,
  "month": 11
}
```

**Job Response:**
```json
{
  "id": 1,
  "period_year": 2026,
  "period_month": 11,
  "status": "PENDING",
  "created_count": 0,
  "skipped_count": 0,
  "error": null,
  "created_at": "2026-11-19T...",
  "started_at": null,
  "finished_at": null
}
```

---

## 5. Business Rules

### 5.1 Kontrak Sewa

**Aturan 1: Satu Kamar Max Satu Kontrak Aktif**
- Sistem mencegah membuat kontrak baru jika kamar sudah punya kontrak dengan status=ACTIVE.
- Kalau ingin ubah penyewa, harus akhiri kontrak lama dulu (status=ENDED).
- Satu penyewa boleh punya banyak kamar aktif sekaligus.

**Aturan 2: Soft Delete Kontrak**
- Tombol "Akhiri Kontrak" set `status=ENDED`, tidak delete record dari DB.
- Kontrak ENDED tidak muncul di list "Kontrak Aktif", tapi ada di history.

### 5.2 Tagihan & Pembayaran

**Aturan 3: Perhitungan Harga Prorata Bulan Pertama**
- Kalau kontrak mulai tgl 15 bulan Oktober, tagihan Oktober = harga × 16/31 (hari 16 sampai 31).
- Tagihan bulan-bulan berikutnya = harga penuh.

**Aturan 4: Denda Keterlambatan (Late Fee)**
- Denda = 2% per minggu, max 10% dari base amount.
- Days late = max(0, hari_ini - due_date).
- Weeks late = ceil(days_late / 7).
- Denda persen = min(weeks_late × 2%, 10%).
- Denda nominal = round(base_amount × denda_persen).
- Late fee dihitung dinamis (snapshot per hari), bukan fixed di tabel.
- **Perubahan:** late_fee di tabel hanya disimpan saat bayar (untuk riwayat).

**Aturan 5: Tagihan Unik Per Periode**
- Database constraint `uq_bill_contract_period` pada (contract_id, period_year, period_month).
- Ketika user click "Generate Tagihan", worker check: kalau tagihan periode itu sudah ada (baik UNPAID/PAID), skip kamar itu.

**Aturan 6: Due Date Tagihan**
- Due date = hari ke-(BILL_DUE_DAY) bulan periode tagihan.
- Misal BILL_DUE_DAY=10 (config), periode November 2026 → due date = 2026-11-10.
- Kalau bulan punya 29/30/31 hari dan due day > hari max, gunakan hari terakhir bulan.

**Aturan 7: Pencatatan Pembayaran (Partial Payment)**
- Satu tagihan boleh dibayar berkali-kali (cicilan).
- Nominal harus > 0 dan **tidak boleh melebihi sisa tagihan** per tanggal bayar (server menolak: "Pembayaran melebihi sisa tagihan"). Kurang atau pas boleh.
- Tagihan yang sudah PAID menolak pembayaran baru (409).
- Saat bayar, denda dihitung per tanggal bayar lalu dibekukan di `bill.late_fee` dan `bill.total`.
- Jika total terbayar >= total, status=PAID dan `paid_at` terisi.

### 5.3 Daftar Tunggakan (Arrears)

**Aturan 8: Kriteria Tunggakan**
- Tagihan UNPAID dengan due_date < hari_ini.
- Computed field: outstanding > 0 dan overdue (hari_ini > due_date).
- Halaman `/arrears` list kontrak yang punya tagihan overdue.

### 5.4 Batch Generate Tagihan

**Aturan 9: Billing Job Flow**
- User click form "Generate Tagihan Bulan Ini" (atau input custom bulan).
- Sistem enqueue BillingJob (status=PENDING) ke tabel job.
- Worker background (loop polling di container terpisah) claim job.
- Worker loop tiap ACTIVE kontrak, create Bill untuk periode itu.
- Kalau Bill sudah ada (uq constraint), skip.
- Kalau terjadi error, job status=FAILED, simpan error message.
- Kalau sukses, job status=COMPLETED, catat jumlah created_count & skipped_count.

---

## 6. Data Model

### 6.1 Database Schema

```sql
-- User (login)
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  email VARCHAR(120) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at DATETIME NOT NULL
);

-- Properti (kompleks kos)
CREATE TABLE properties (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL,
  address VARCHAR(255) NOT NULL,
  created_at DATETIME NOT NULL
);

-- Kamar
CREATE TABLE rooms (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  property_id INTEGER NOT NULL FOREIGN KEY (properties.id),
  number VARCHAR(20) NOT NULL,
  monthly_price INTEGER NOT NULL,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uq_room_property_number (property_id, number)
);

-- Penyewa
CREATE TABLE tenants (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL,
  phone VARCHAR(30) NOT NULL,
  email VARCHAR(120),
  created_at DATETIME NOT NULL
);

-- Kontrak Sewa
CREATE TABLE contracts (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  room_id INTEGER NOT NULL FOREIGN KEY (rooms.id),
  tenant_id INTEGER NOT NULL FOREIGN KEY (tenants.id),
  start_date DATE NOT NULL,
  end_date DATE,
  monthly_price INTEGER NOT NULL,
  status VARCHAR(10) NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, ENDED
  created_at DATETIME NOT NULL,
  INDEX idx_room_status (room_id, status)
);

-- Tagihan
CREATE TABLE bills (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  contract_id INTEGER NOT NULL FOREIGN KEY (contracts.id),
  period_year INTEGER NOT NULL,
  period_month INTEGER NOT NULL,
  base_amount INTEGER NOT NULL,
  late_fee INTEGER NOT NULL DEFAULT 0, -- late fee saat dibayar
  total INTEGER NOT NULL,
  due_date DATE NOT NULL,
  status VARCHAR(10) NOT NULL DEFAULT 'UNPAID', -- UNPAID, PAID
  paid_at DATE,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uq_bill_contract_period (contract_id, period_year, period_month)
);

-- Pembayaran
CREATE TABLE payments (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  bill_id INTEGER NOT NULL FOREIGN KEY (bills.id),
  amount INTEGER NOT NULL,
  paid_on DATE NOT NULL,
  method VARCHAR(30) NOT NULL DEFAULT 'TRANSFER', -- teks bebas, belum ada daftar pilihan di backend
  created_at DATETIME NOT NULL
);

-- Billing Job (antrean worker)
CREATE TABLE billing_jobs (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  period_year INTEGER NOT NULL,
  period_month INTEGER NOT NULL,
  status VARCHAR(12) NOT NULL DEFAULT 'PENDING', -- PENDING, PROCESSING, COMPLETED, FAILED
  created_count INTEGER NOT NULL DEFAULT 0,
  skipped_count INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  created_at DATETIME NOT NULL,
  started_at DATETIME,
  finished_at DATETIME
);
```

### 6.2 Relasi & Views

```
User: standalone

Property ←→ Room ←→ Contract ←→ Bill ←→ Payment
                         ↓
                      Tenant

BillingJob: queue processor
```

---

## 7. Architecture & Tech Stack

### 7.1 Stack

| Layer | Tech |
|-------|------|
| **Backend** | Python 3.11+, Flask 3.1.3 |
| **ORM** | SQLAlchemy 2.1.8 |
| **Migration** | Flask-Migrate 4.1.0 (alembic 1.20.1) |
| **Database** | MySQL 8.4 (production), SQLite in-memory (test) |
| **Worker** | Python loop polling (async via signal safe) |
| **Web Server** | gunicorn 27.0.1 (production), Flask dev (test) |
| **Testing** | pytest 9.2.0 |
| **Containerization** | Docker + Docker Compose |
| **Frontend** | Flask Jinja2 templates (HTML/CSS, plain JS) |

### 7.2 Project Structure

```
Tubes/
├── kosanhub/
│   ├── __init__.py              (Flask app factory)
│   ├── auth.py                  (login, session, guard)
│   ├── config.py                (config class)
│   ├── errors.py                (exception class)
│   ├── models.py                (SQLAlchemy model)
│   ├── utils.py                 (helper: clean_str, parse_*)
│   ├── seeder.py                (data seed untuk dev)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── admin.py             (CRUD form route)
│   │   ├── web.py               (halaman publik/dashboard)
│   │   ├── health.py            (healthcheck)
│   │   ├── [entities]/          (blueprint per entitas, API)
│   ├── services/
│   │   ├── billing.py           (hitung denda, prorata, etc)
│   │   ├── contracts.py         (create/end kontrak, bayar tagihan)
│   │   ├── jobs.py              (enqueue/claim/process job)
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── form.html
│   │   ├── [page].html
│   │   └── _macros.html
│   └── static/
│       └── style.css
├── tests/
│   └── test_kosanhub.py         (pytest, 17 test cases)
├── migrations/                   (Flask-Migrate)
├── worker.py                     (background job processor)
├── wsgi.py                       (gunicorn entry point)
├── requirements.txt              (pip package)
├── Dockerfile                    (multi-stage)
├── compose.yaml                  (dev, build lokal)
├── compose.prod.yaml             (prod, pull from Hub)
├── .env.example                  (template config)
└── README.final.md
```

### 7.3 Deployment

**Development:**
```bash
cp .env.example .env
# Edit .env: DB_PASSWORD, MYSQL_ROOT_PASSWORD
docker compose up -d --build
# App: http://localhost:8000
```

**Production (via Jenkins):**
```bash
docker compose -f compose.prod.yaml up -d
# Image dari Docker Hub: dockeradli/kosanhub:[BUILD_NUMBER]
```

---

## 8. Error Handling & Validation

### 8.1 Input Validation

- **Email**: format regex, lowercase, unique
- **Phone**: 8-15 digit angka (regex `^\+?[0-9]{8,15}$`)
- **Password**: min 8 char (saat create/change)
- **Number field**: integer, min/max check
- **Date field**: valid ISO date
- **Text field**: strip whitespace, max length, no SQL injection (ORM-safe)

### 8.2 Business Logic Errors

| Error | HTTP Code | Message |
|-------|-----------|---------|
| Email tidak valid | 400 | "email tidak valid" |
| Email sudah ada | 409 | "email [email] sudah ada" |
| Kamar punya ACTIVE kontrak | 409 | "kamar sudah memiliki kontrak aktif" |
| Tagihan periode sudah ada | 409 | "tagihan periode [month]/[year] sudah ada" |
| Data FK tidak ditemukan | 404 | "[Entitas] tidak ditemukan" |
| Properti punya kamar/kontrak | 409 | "properti memiliki kamar dengan riwayat kontrak, tidak dapat dihapus" |
| Password lama salah | 400 | "Password lama salah" |

### 8.3 Flash Message (Form)

- **Success**: "Properti disimpan.", "Pembayaran dicatat.", dll → category "ok"
- **Error**: "Data bentrok dengan data yang sudah ada.", "Password minimal 8 karakter." → category "error"

---

## 9. Security Considerations

### 9.1 Authentication & Authorization

- **Session-based**: Flask session (cookie HttpOnly + SameSite)
- **API Basic Auth**: HTTP Basic (`Authorization: Basic base64(email:password)`)
- **CSRF Protection**: token custom di session (`csrf_token()` di auth.py), wajib pada semua POST web/admin
- **Admin Guard**: @admin_required decorator, check session atau HTTP Basic

### 9.2 Data Security

- **Password**: hashed via werkzeug.security.generate_password_hash (scrypt)
- **Config Secret**: SECRET_KEY di .env, tidak di-commit
- **API Response**: tidak include password, hanya field yang perlu

### 9.3 Container Security

- **Layers**: multi-stage Dockerfile (test + production)
- **Image**: FROM python:3.11-slim (tidak root)
- **Env Vars**: .env tidak di-commit, .env.example template saja
- **.dockerignore**: exclude .git, .venv, __pycache__, test

---

## 10. Testing & QA

### 10.1 Unit & Integration Test

- **Framework**: pytest
- **Fixture**: app (TestingConfig SQLite in-memory), client (login), seed_data
- **Coverage**: 17 test case mencakup:
  - Auth (login, logout, password change)
  - Form validation (CRUD properti, kamar, penyewa, kontrak, user)
  - API (GET terbuka, POST/PUT/DELETE admin-only)
  - Business rules (1 kamar 1 kontrak, denda, unique bill, partial payment)
  - Multi-room tenant (1 penyewa, banyak kamar)
  - Page render & permission

### 10.2 Smoke Test (Jenkins)

```bash
# Health check
curl http://localhost:8000/health

# API test (HTTP Basic)
curl -u admin@gmail.com:[PASSWORD] http://localhost:8000/api/properties
curl -X POST -u admin@gmail.com:[PASSWORD] http://localhost:8000/api/properties -d "name=Kos+Test&address=Jl.+Test"

# Form test (session-based)
curl -b cookies.txt -c cookies.txt http://localhost:8000/login -d "email=admin@gmail.com&password=[PASSWORD]"
curl -b cookies.txt http://localhost:8000/properties
```

---

## 11. Known Limitations & Future Work

### 11.1 MVP Scope (Sudah Ada)
- ✅ CRUD properti, kamar, penyewa, kontrak
- ✅ Tagihan bulanan otomatis (via job worker)
- ✅ Denda otomatis
- ✅ Pencatatan pembayaran (partial)
- ✅ Daftar tunggakan
- ✅ User management (create, delete, change password)
- ✅ API untuk automation/testing
- ✅ Docker local build & production ready

### 11.2 Belum Ada (Out of Scope untuk Tubes)
- ❌ Frontend React/Vue (saat ini: Flask Jinja template)
- ❌ SMS/Email notifikasi (manual via admin)
- ❌ Multi-property permission (semua user admin penuh)
- ❌ Report/export Excel
- ❌ Payment gateway integration (manual entry)
- ❌ Notification service
- ❌ Advanced permission role (user, manager, super admin)

### 11.3 Potential Improvements
- Peran user (admin, supervisor, operator)
- Multi-language support
- Lokalisasi mata uang & format tanggal
- Caching (Redis) untuk dashboard
- Webhook untuk notifikasi event
- Soft delete dengan restore untuk data yang dihapus
- Audit log (siapa ubah apa kapan)

---

## 12. Checklist Feature vs UI Page

| Feature | Model | Service | API | Web Page | Form Admin | Test |
|---------|-------|---------|-----|----------|-----------|------|
| CRUD Properti | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| CRUD Kamar | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| CRUD Penyewa | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Buat Kontrak | ✅ | ✅ | ✅ | ✅ (tombol "+ Sewakan kamar" di /contracts) | ✅ | ✅ |
| Akhiri Kontrak | ✅ | ✅ | ✅ | ✅ (tombol di /contracts, confirm() bawaan browser) | ✅ | ✅ |
| Generate Tagihan (Batch) | ✅ | ✅ | ✅ | ✅ (form di /jobs saja, belum di /bills) | ✅ | ✅ |
| Tagihan List | ✅ | - | ✅ | ✅ | - | ✅ |
| Bayar Tagihan | ✅ | ✅ | ✅ | ✅ (tombol Bayar di tabel tagihan) | ✅ | ✅ |
| Pembayaran List | ✅ | - | ✅ | ✅ | - | ✅ |
| Tunggakan List | ✅ | - | ✅ | ✅ | - | ✅ |
| Job List | ✅ | ✅ | ✅ | ✅ | - | ✅ |
| Kelola User | ✅ | - | ❌ | ✅ | ✅ | ✅ |
| Profile (Change Password) | ✅ | - | ❌ | ✅ | ❌ | ✅ |

**Legend:**
- ✅ = feature sudah lengkap (code ada, test lulus)
- ❌ = feature belum ada / belum diimplementasi

**Catatan (dikoreksi setelah dicek ke kode):**
- Semua fitur wajib sudah punya tombol/halaman. Yang belum: tombol Generate Tagihan di /bills, dan modal konfirmasi kustom (saat ini `confirm()` browser).
- Kolom "Test" belum diverifikasi per baris; yang pasti hanya total 17 test lulus.
- Pesan error di Bagian 8.2 bersifat indikatif, belum dicocokkan satu per satu dengan teks di kode.

---

## 13. Release & Handoff Notes

**Version 1.0 Deliverable (Tubes):**
- Backend Flask + MySQL + Worker
- 10 halaman web (dashboard, CRUD list, form admin)
- 7 endpoint API + internal service
- 17 test case (pytest)
- Docker local build + compose.prod.yaml untuk deployment
- README & PRD

**Next Phase (Post-MVP):**
- React frontend (optional, dapat di-add kemudian)
- Dashboard enhancement (chart, export)
- Notification service (SMS/Email)
- Advanced permission & audit log

---

**Approval & Sign-off:**
- [ ] Naufal (Backend) — 2026-11-19
- [ ] Noval (Container) — TBD
- [ ] Gusti (Jenkins) — TBD
- [ ] Haydar (QA) — TBD

