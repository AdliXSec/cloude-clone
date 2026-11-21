# Setup Jenkins Lokal untuk KosanHub Pipeline

> Panduan setup Jenkins di mesin Linux lokal, mengikuti Modul Praktikum 1 & Tugas Besar 1 K12.

## 1. Prasyarat

```bash
# Verifikasi persyaratan
docker --version           # >= 20.10
docker compose version     # >= 2.0
git --version             # >= 2.30
python3 --version         # >= 3.9
```

## 2. Jalankan Jenkins di Docker

Buat volume untuk Jenkins (agar config tetap saat container restart):

```bash
docker volume create jenkins_home
```

Jalankan Jenkins:

```bash
docker run -d \
  --name jenkins \
  -p 8080:8080 \
  -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(which docker):/usr/bin/docker \
  --group-add $(getent group docker | cut -d: -f3) \
  jenkins/jenkins:lts
```

> **Catatan:**
> - `-v /var/run/docker.sock:/var/run/docker.sock` → Akses Docker daemon dari Jenkins
> - `--group-add $(getent group docker | cut -d: -f3)` → Jenkins user bisa akses docker group
> - Port 8080 → Jenkins UI
> - Port 50000 → Jenkins agent communication

Lihat initial admin password:

```bash
docker logs jenkins | grep -A 5 "Please use the following password"
```

Akses Jenkins:

```
http://localhost:8080
```

Login dengan `admin` dan password dari logs. Pilih "Install suggested plugins".

## 3. Setup Git di Jenkins

Manage Jenkins → Tools → Git:

```
Path to Git executable: /usr/bin/git
```

## 4. Setup Credentials

### 4.1 Docker Hub Credentials

- Buka Manage Jenkins → Credentials → (Global) → Add Credentials
- **Kind:** Username with password
- **Username:** `dockeradli` (ganti dengan Docker Hub username Anda)
- **Password:** `<Docker Hub PAT atau password>`
- **ID:** `dockerhub-kosanhub` (WAJIB sesuai Jenkinsfile)
- **Description:** Docker Hub - KosanHub
- Klik Create

### 4.2 GitHub Credentials (opsional, jika repo private)

- **Kind:** Secret text
- **Secret:** `<GitHub PAT>`
- **ID:** `github-kosanhub`
- **Description:** GitHub PAT - KosanHub
- Klik Create

## 5. Setup Ngrok (untuk testing webhook publik)

Unduh Ngrok:

```bash
cd /tmp
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.zip
unzip ngrok-v3-stable-linux-amd64.zip
sudo mv ngrok /usr/local/bin/
```

Jalankan Ngrok di terminal terpisah:

```bash
ngrok http 8080
```

Catat URL publik, misalnya: `https://abc-123-xyz.ngrok-free.app`

## 6. Setup GitHub Webhook

Di repository GitHub:

1. Settings → Webhooks → Add webhook
2. **Payload URL:** `https://abc-123-xyz.ngrok-free.app/github-webhook/`
3. **Content type:** `application/json`
4. **Events:** Push events + Pull requests
5. Klik Add webhook

Verifikasi di Recent Deliveries harus ada response `200 OK`.

## 7. Buat Pipeline Job di Jenkins

1. Jenkins UI → New Item
2. **Item name:** `kosanhub-pipeline`
3. **Type:** Pipeline
4. Klik OK

Di bagian Pipeline:

- **Definition:** Pipeline script from SCM
- **SCM:** Git
- **Repository URL:** `https://github.com/AdliXSec/CloudCom-KosanHub.git`
- **Branch:** `main`
- **Script Path:** `Jenkinsfile`

Klik Save.

## 8. Verifikasi Setup

Trigger build manual:

```
Jenkins → kosanhub-pipeline → Build Now
```

Cek console log. Seharusnya stage Checkout OK.

Trigger otomatis via webhook:

```bash
# Di repo lokal
git commit --allow-empty -m "Test webhook"
git push origin main
```

Lihat di Jenkins → kosanhub-pipeline. Build seharusnya trigger otomatis (cek Recent Deliveries di GitHub juga).

## 9. Troubleshooting

### Jenkins tidak bisa akses Docker

```bash
# Verifikasi docker socket
ls -la /var/run/docker.sock

# Restart Jenkins
docker restart jenkins
```

### Webhook tidak trigger

- Cek Ngrok terminal apakah ada request dari GitHub
- Verifikasi payload URL di GitHub webhook (sama dengan Ngrok URL?)
- Cek Jenkins → Manage Jenkins → System → GitHub Server (jika configured)

### Credential tidak ditemukan

```bash
# Verifikasi credential ID di Jenkins
# Harus match: dockerhub-kosanhub
```

### Build timeout

Tingkatkan timeout di Jenkinsfile atau di Jenkins:

```
Manage Jenkins → System → Build discarder (global) → Keep builds for 30 days
```

## 10. Akses via Ngrok untuk Dosen

Share link publik Ngrok ke dosen:

```
https://abc-123-xyz.ngrok-free.app
```

Username: `admin`
Password: Gunakan initial admin password atau reset (see below).

### Reset Admin Password (jika lupa)

```bash
docker exec jenkins bash -c 'cat /var/jenkins_home/secrets/initialAdminPassword'
```

## 11. Buat Akun Dosen (untuk penilaian)

1. Manage Jenkins → Security → Manage Users
2. Create User:
   - **Username:** `dosen`
   - **Password:** `exam2026`
   - **Full Name:** Dosen Pengampu
   - **Email:** `dosen@cloud.ac.id`
3. Klik Create User

> Catat username/password untuk laporan.

## 12. Test Pipeline Lokal

```bash
# Di repo local
cd ~/Praktikum/CloudCom/Tubes

# Pastikan .env ada (copy dari .env.example jika perlu)
cp .env.example .env

# Edit .env dengan nilai lokal jika perlu
nano .env

# Push ke GitHub (trigger Jenkins via webhook)
git add Jenkinsfile JENKINS_SETUP.md
git commit -m "Add Jenkinsfile for CI/CD pipeline"
git push origin main

# Monitor di Jenkins UI
# http://localhost:8080/job/kosanhub-pipeline/

# Atau trigger manual
# Jenkins → kosanhub-pipeline → Build Now
```

## 13. Verifikasi Aplikasi Setelah Deploy

```bash
# Cek container status
docker compose ps

# Health check
curl -s http://localhost:8000/health | jq

# API test (dengan auth)
curl -s -u admin@gmail.com:dev http://localhost:8000/api/jobs | jq
```

## 14. Simpan Credentials Aman

**JANGAN COMMIT:**
- `.env` (sudah di .gitignore)
- Jenkins config files

**BOLEH SHARE:**
- `.env.example` (template saja, tanpa nilai rahasia)
- Jenkinsfile (tidak ada token atau password di dalamnya)
- Link Ngrok publik (untuk dosen)

---

**Setup complete!** Pipeline siap untuk testing lokal. Setiap push ke GitHub akan trigger build otomatis via webhook.

Untuk production, gunakan `compose.prod.yaml` dan jalankan Jenkins di server dengan domain tetap (bukan Ngrok).
