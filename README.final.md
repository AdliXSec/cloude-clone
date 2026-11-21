# KosanHub – Backend & Sistem Tagihan Bulanan Kos (K12)

KosanHub adalah aplikasi manajemen sewa kos dan tagihan bulanan dengan antrean background worker, dibangun menggunakan **Flask**, **SQLAlchemy**, dan **MySQL 8**.

Aplikasi ini dibuat untuk memenuhi **Tugas Besar 1 Komputasi Awan (DevOps CI/CD Pipeline Jenkins)** Kelompok 4 (Studi Kasus K12).

---

## 👥 Tim Kelompok 4
- **Naufal Syahruradli** (102062400103) – Tech Lead & Backend Developer
- **Moch Noval Eka Saputra** (102062400053) – Containerization Engineer
- **Gusti Prabu Basudewa Krista** (102062400145) – DevOps Engineer
- **Haydar Triprakoso Aridiaz** (102062400122) – QA Engineer & Technical Writer

---

## 🛠️ Fitur & 4 Aturan Bisnis
1. **Aturan 1 (Kamar Tunggal):** Satu kamar hanya boleh memiliki 1 kontrak sewa yang berstatus `ACTIVE` dalam satu waktu.
2. **Aturan 2 (Prorata Masuk):** Tagihan bulan pertama dihitung secara proporsional sesuai hari tersisa di bulan tersebut.
3. **Aturan 3 (Denda Bertingkat):** Denda keterlambatan 2% per minggu berjalan, maksimal 10% (cap di minggu ke-5).
4. **Aturan 4 (Idempotensi Tagihan):** Tagihan hanya boleh terbit satu kali untuk kombinasi kontrak dan periode tahun-bulan yang sama.

### ⚡ Tantangan Khusus K12
- Antrean job tagihan berbasis database (`billing_jobs`).
- Worker background (`worker.py`) memproses tagihan dari antrean secara non-blocking.
- Docker image yang sama digunakan untuk container web service dan worker service dengan perintah berbeda.

---

## 🚀 Menjalankan Secara Lokal

### 1. Prasyarat
- Python 3.11+
- Virtual Environment

### 2. Setup & Instalasi
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # runtime + pytest
cp .env.example .env
```

### 3. Menjalankan Unit & Integration Test
```bash
pytest -v
```

Test memakai SQLite in-memory (tidak butuh MySQL). Ada 6 test:
- `test_rule_1_room_single_active_contract` — Verifikasi 1 kamar = 1 kontrak ACTIVE
- `test_rule_2_prorated_first_month` — Tagihan bulan pertama prorata sesuai tanggal masuk
- `test_rule_3_late_fee_calculation` — Denda 2% per minggu, maksimal 10%
- `test_rule_4_unique_monthly_bill` — Idempotensi tagihan (tidak boleh duplikat periode)
- `test_health_endpoint` — Endpoint `/health` return 200 dengan status database
- `test_k12_worker_processes_billing_queue` — Worker memproses job dari antrean hingga COMPLETED

### 4. Menjalankan Server Web & Worker
Jalankan Web Server:
```bash
gunicorn -b 0.0.0.0:8000 --workers 2 --worker-class gthread --threads 4 wsgi:app
```
Jalankan Worker (di terminal terpisah):
```bash
python worker.py
```

---

## 🐳 Menjalankan dengan Docker Compose

### Dua file compose
| File | Image | Dipakai untuk |
|------|-------|---------------|
| `compose.yaml` | Build lokal dari `Dockerfile` (stage `production`, pytest ikut jalan saat build) | Development lokal dan pembuktian pengerjaan |
| `compose.prod.yaml` | `${APP_IMAGE}` dari Docker Hub (default `dockeradli/kosanhub:latest`) | Production / deploy pipeline Jenkins |

Isi keduanya sama (db, app, worker, network, healthcheck); beda hanya `build:` vs `image:`.

### Development Lokal (Build dari Source)
```bash
cp .env.example .env
# Edit .env, isi DB_PASSWORD dan MYSQL_ROOT_PASSWORD dengan nilai aman
docker compose up -d --build
```

### Production (Dari Docker Hub)
```bash
docker compose -f compose.prod.yaml pull
docker compose -f compose.prod.yaml up -d
```

Container app otomatis menjalankan `flask db upgrade`, lalu `flask seed` (jika `AUTO_SEED=1`), lalu gunicorn. Worker baru start setelah app healthy, jadi migrasi pasti sudah selesai.

### Env Variables Penting
| Variabel | Nilai default | Keterangan |
|----------|---------------|-----------|
| `DB_HOST` | `db` | Host database (nama service Compose) |
| `DB_NAME` | `kosanhub` | Nama database |
| `DB_USER` | `kosanhub` | User database |
| `DB_PASSWORD` | *(tidak ada)* | Password database — **WAJIB diisi** di `.env` |
| `MYSQL_ROOT_PASSWORD` | *(tidak ada)* | Password root MySQL — **WAJIB diisi** di `.env` |
| `APP_IMAGE` | `dockeradli/kosanhub:latest` | Hanya `compose.prod.yaml` (diubah Jenkins jadi tag `BUILD_NUMBER`) |
| `APP_PORT` | `8000` | Port aplikasi di host |
| `AUTO_SEED` | `1` | Jalankan seeder otomatis saat app start (idempoten, aman diulang) |
| `BILL_DUE_DAY` | `10` | Tanggal jatuh tempo tagihan setiap bulan |
| `WORKER_POLL_SECONDS` | `3` | Interval worker polling job (detik) |

### Cek Status Service
Setelah `up -d`, verifikasi semua service healthy:
```bash
docker compose ps
# db dan app: "healthy"; worker: "running" (worker tidak punya healthcheck)

# Test koneksi aplikasi
curl -s http://localhost:8000/health | jq .
# Response: {"status":"ok","database":"connected"}
```

### Jalankan Smoke Test Lokal
```bash
# Trigger pembuatan tagihan
curl -u "$ADMIN_EMAIL:$ADMIN_PASSWORD" -X POST http://localhost:8000/api/jobs/generate-bills \
  -H 'Content-Type: application/json' \
  -d '{"year":2026,"month":11}'

# Tunggu ~5 detik, worker akan memprosesnya
sleep 5

# Cek hasil (status COMPLETED = sukses)
curl -s -u "$ADMIN_EMAIL:$ADMIN_PASSWORD" http://localhost:8000/api/jobs/1 | jq .

# Lihat tagihan yang dibuat
curl -s -u "$ADMIN_EMAIL:$ADMIN_PASSWORD" http://localhost:8000/api/bills | jq .
```

### Shutdown & Cleanup
```bash
# Stop dan hapus container, network, volume
docker compose down -v

# Jika ingin simpan data database, gunakan:
docker compose down
```

---

## 📦 Desain Container

### Dockerfile (multi-stage)
| Stage | Isi | Fungsi |
|---|---|---|
| `base` | `python:3.11-slim` + `requirements.txt` + kode app | Dependency runtime saja (tanpa pytest) |
| `test` | `base` + `requirements-dev.txt` + `tests/`, `RUN python -m pytest -q` | Quality gate: test gagal = build gagal |
| `production` | `base` + penanda dari stage `test`, user non-root `appuser` (uid 10001), gunicorn port 8000 | Image yang di-push ke Docker Hub |

Stage `production` menyalin file penanda dari stage `test` (`COPY --from=test`). Karena itu `docker build --target production` selalu menjalankan test lebih dulu, dan image production tidak akan pernah jadi kalau ada test yang gagal.

```bash
docker build --target test -t kosanhub:test .          # hanya jalankan test
docker build --target production -t kosanhub:local .   # test + image production
```

### compose.yaml
| Service | Image | Command | Network | Keterangan |
|---|---|---|---|---|
| `db` | `mysql:8.4` | default | `backend` | Volume `db_data`, healthcheck `mysqladmin ping`, tidak ada port ke host |
| `app` | `${APP_IMAGE}` | migrasi, seed, gunicorn | `frontend` + `backend` | Satu-satunya service yang membuka port (8000), healthcheck `/health` |
| `worker` | `${APP_IMAGE}` (image sama) | `python worker.py` | `backend` | Tantangan K12: memproses antrean `billing_jobs` |

- Network `backend` memakai `internal: true`, sehingga DB dan worker tidak bisa diakses dari luar dan tidak bisa keluar ke internet.
- Semua service memakai `restart: unless-stopped`.
- `app` menunggu `db` healthy; `worker` menunggu `db` dan `app` healthy (`depends_on: condition: service_healthy`).
- `compose.yaml` build image lokal dari `Dockerfile`. Deploy di pipeline memakai `compose.prod.yaml`, sehingga yang jalan adalah image hasil pipeline dari Docker Hub.

### Keamanan Credential
- Password hanya ada di `.env` (masuk `.gitignore` dan `.dockerignore`); repo hanya berisi `.env.example`.
- Compose menolak start bila `DB_PASSWORD` / `MYSQL_ROOT_PASSWORD` belum diisi.
- Image tidak berisi `.env`, `tests/`, `.git`, maupun `.venv`.
- Push ke Docker Hub hanya dilakukan Jenkins lewat Jenkins Credentials (`withCredentials`), bukan dari laptop anggota.

---

## 📡 Ringkasan REST API

| Method | Endpoint | Deskripsi |
|---|---|---|
| `GET` | `/` | Halaman web sederhana |
| `GET` | `/health` | Health check koneksi database (200 / 503) |
| `GET`, `POST` | `/api/properties` | List / tambah properti kos |
| `GET`, `PUT`, `DELETE` | `/api/properties/<id>` | Detail / ubah / hapus properti |
| `GET`, `POST` | `/api/rooms` | List / tambah kamar |
| `GET`, `PUT`, `DELETE` | `/api/rooms/<id>` | Detail / ubah / hapus kamar |
| `GET`, `POST` | `/api/tenants` | List / daftar penyewa |
| `GET`, `PUT`, `DELETE` | `/api/tenants/<id>` | Detail / ubah / hapus penyewa |
| `GET`, `POST` | `/api/contracts` | List / buat kontrak (aturan 1: 409 jika kamar sudah punya kontrak aktif) |
| `GET` | `/api/contracts/<id>` | Detail kontrak |
| `POST` | `/api/contracts/<id>/end` | Akhiri kontrak |
| `GET`, `POST` | `/api/bills` | List / buat tagihan manual (aturan 2 dan 4) |
| `GET` | `/api/bills/<id>` | Detail tagihan |
| `GET` | `/api/bills/arrears` | Daftar tunggakan + denda (aturan 3) |
| `GET`, `POST` | `/api/payments` | List / catat pembayaran |
| `POST` | `/api/jobs/generate-bills` | Masukkan job tagihan bulanan ke antrean (202, K12) |
| `GET` | `/api/jobs` | List job antrean |
| `GET` | `/api/jobs/<id>` | Status job (PENDING / PROCESSING / COMPLETED / FAILED) |
