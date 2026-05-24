# JORINOVA NEXUS — Deployment Guide

Complete, no-skip runbook from zero to a clinician signing in.

## Architecture in one paragraph

```
                       ┌──────────────┐
   user browser  ───►  │  nginx :443  │  ──►  /          ─► web (Next.js)
                       │              │       /api/*     ─► api (FastAPI)
                       │              │       /static/*  ─► (cached)
                       │              │       /media/*   ─► (signed)
                       └──────────────┘
                              │
                              ├──►  api  (FastAPI + gunicorn) ─► postgres
                              │                                ─► redis
                              │                                ─► ollama (optional)
                              └──►  web  (Next.js standalone)
```

Three compose profiles, pick the one that matches the site:

| Profile  | What's in it                                          | Use for                       |
|----------|-------------------------------------------------------|-------------------------------|
| offline  | postgres + api                                        | site with no internet, no AI  |
| standard | postgres + api + redis + ollama + web (exposed)       | recommended pilot deployment  |
| full     | standard + nginx (HTTPS) + celery + flower            | production with a domain      |

## Quick start — `standard` profile (pilot)

```bash
git clone https://github.com/jorinova/JORINOVA.git
cd JORINOVA

# 1. Production secrets
cp backend/.env.example backend/.env.production
python backend/scripts/generate_secrets.py >> backend/.env.production
$EDITOR backend/.env.production               # fill DB_PASSWORD, ANTHROPIC_API_KEY, EMAIL_*

# 2. Deploy
./scripts/deploy.sh standard

# 3. First-run wizard
open http://localhost:3000/install
```

The install wizard is a 4-step branded flow:
1. **Choose system language** (English / Français / Kinyarwanda) — locked
   as the default for everyone signing in. Each user can override later.
2. **Hospital details** (name, district, contact)
3. **First administrator account** (super-admin)
4. **Done** → lands on `/login`

Visit `/install` again later and it refuses with 409 — setup runs once.

## Walk-in patient registration

The standard path is OCR + LIS auto-mapping ([`/modules/lis_mapping`](frontend/app/modules/lis_mapping/page.tsx))
— it auto-registers the patient as a side effect of mapping the form.

For walk-ins (no form, no reception flow, emergency arrival, paper-only
site), go to **[`/modules/patients/new`](frontend/app/modules/patients/new/page.tsx)**:

1. Type family name + gender (minimum)
2. Click **Check duplicates** — POSTs to `/api/v1/patients/check-duplicate`
   matching by NID, phone, and name+DOB
3. If hits: pick "Use existing patient" or tick "register anyway"
4. **Register** → POSTs to `/api/v1/patients/` and returns PID + LID

Available from the **Patients** module header.

## Files that matter

| File                                | Why it matters                                          |
|-------------------------------------|---------------------------------------------------------|
| `docker-compose.yml`                | Service definitions + profiles                          |
| `backend/Dockerfile`                | FastAPI production image                                |
| `frontend/Dockerfile`               | Next.js multi-stage image (standalone output, ~280 MB)  |
| `backend/.env.production`           | All secrets — **never commit**                          |
| `frontend/.env.production.example`  | Template for frontend env (mostly NEXT_PUBLIC_API_URL)  |
| `nginx/nginx.conf`                  | HTTPS termination, rate limits, CSP, /api vs / routing  |
| `scripts/deploy.sh`                 | One-shot deploy for any profile                         |
| `scripts/generate_secrets.py`       | Random SECRET_KEY + DB_PASSWORD + ENCRYPTION_KEY        |

## Full production (`full` profile) — TLS + domain

```bash
# 0. DNS A record points at the server, e.g. nexus.hospital.rw → 41.x.x.x

# 1. Edit nginx config: replace nexus.hospital.rw with your domain
$EDITOR nginx/nginx.conf

# 2. Edit production env
$EDITOR backend/.env.production

# 3. Bring stack up WITHOUT nginx first (so certbot can reach port 80)
docker compose --profile standard up -d postgres api web

# 4. Issue cert
docker compose run --rm certbot certonly --webroot \
  -w /var/www/certbot \
  -d nexus.hospital.rw -d www.nexus.hospital.rw \
  --email ops@hospital.rw --agree-tos --no-eff-email

# 5. Bring up nginx
./scripts/deploy.sh full

# 6. Install wizard
open https://nexus.hospital.rw/install
```

`certbot` auto-renews every 12 hours after that.

## What gets deployed per profile

**offline**
- `postgres`, `migrate` (once-off), `api` (localhost only)

**standard** (everything in offline plus)
- `redis`, `ollama` (downloads phi3:mini on first boot)
- `api-exposed` (port 8000 on 0.0.0.0), `web-exposed` (port 3000 on 0.0.0.0)

Open `http://<host>:3000`.

**full** (everything in standard minus the *-exposed variants, plus)
- `nginx` (port 80 + 443, TLS, CSP, rate-limiting)
- `web` and `api` behind nginx, internal-only
- `worker`, `beat` (Celery), `flower` (Celery monitoring, internal-only)
- `certbot` (Let's Encrypt renewal)

## Healthchecks

```bash
docker compose ps                              # one-line per service
docker compose logs -f api web                 # live tail
docker compose exec api bash                   # shell into api
docker compose exec postgres psql -U $DB_USER  # db REPL
```

States:
- `healthy`   — last healthcheck passed
- `starting`  — booting (~30s)
- `unhealthy` — failing — `docker compose logs <service>`

## Operational tasks

### Apply DB migrations after pulling new code
```bash
docker compose --profile standard up -d migrate
```

### Rotate secrets
1. Generate new SECRET_KEY: `python -c 'import secrets; print(secrets.token_hex(32))'`
2. Update `backend/.env.production`
3. `docker compose --profile standard restart api web`

All sessions invalidated — users sign in again.

### Backups
```bash
docker compose exec postgres \
  pg_dump -U $DB_USER $DB_NAME | gzip > /backups/nexus-$(date +%F).sql.gz
```

### Add the JORINOVA logo for the first time
Drop `frontend/public/logo/jorinova-nexus.png` then:
```bash
docker compose --profile standard build web && docker compose --profile standard up -d web
```

## What the user sees on first visit

```
GET /              → web container. Next.js root page reads
                     /api/v1/setup/status. If needs_setup=true, redirect to
                     /install. Else, /login (or /dashboard if a session
                     cookie is present).
```

Role-based landing after login (see [`role-routes.ts`](frontend/app/lib/role-routes.ts)):
- `super_admin` / `lab_manager` / `scientist` → `/dashboard`
- `doctor` → `/portal/doctor`
- `rbc_admin` → `/portal/rbc`
- `receptionist` → `/modules/lis_mapping`
- `pathologist` → `/modules/laboratory`

## Troubleshooting cheat sheet

| Symptom                                | Likely cause                                      | Fix                                                |
|----------------------------------------|---------------------------------------------------|----------------------------------------------------|
| `/install` keeps appearing             | DB was wiped or never seeded                      | Run wizard once; data persists in `postgres_data`  |
| `502 Bad Gateway` from nginx           | `api` or `web` container not healthy              | `docker compose logs api web`                      |
| CORS error in browser console          | `ALLOWED_HOSTS` doesn't include the host          | Edit `backend/.env.production`, restart `api`      |
| Login OK but `/me` returns 401         | `SECRET_KEY` was rotated                          | All users sign in again                            |
| Ollama 500: "unable to allocate buffer"| Host RAM exhausted                                | Set `ANTHROPIC_API_KEY` and use cloud cascade      |
| Logo / profile photo not showing       | Asset not copied into `frontend/public/logo/`     | Drop file, rebuild web                             |
| Session auto-logs-out fast             | 5-min idle timeout (by design)                    | `IDLE_MS` in [`AppShell.tsx`](frontend/app/components/AppShell.tsx) |

## Reverting / wiping for a fresh start

```bash
docker compose --profile standard down       # stop, keep data
docker compose --profile standard down -v    # stop AND DELETE ALL DATA
```

After `-v`, the next `/install` wizard appears again because the DB is empty.
