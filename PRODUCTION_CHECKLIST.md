# JORINOVA NEXUS ALIS-X — Production Deployment Checklist

## Step 1: Prepare the server (Ubuntu 22.04 LTS recommended)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose v2
sudo apt install docker-compose-plugin

# Clone the repository
git clone https://github.com/jorinova/nexus.git /opt/nexus
cd /opt/nexus
```

## Step 2: Generate production secrets

```bash
python3 scripts/generate_secrets.py
# Copy the output into backend/.env.production
```

## Step 3: Configure environment

```bash
cp backend/.env.production backend/.env.production.bak  # backup
nano backend/.env.production

# Change these (minimum):
# SECRET_KEY=<generated>
# DB_PASSWORD=<generated>
# REDIS_PASSWORD=<generated>
# ALLOWED_HOSTS=nexus.yourhospital.rw
# ANTHROPIC_API_KEY=<your key> (optional)
# AT_API_KEY=<Africa's Talking key> (for SMS)
```

## Step 4: Deploy

```bash
# Standard (recommended first deploy):
./scripts/deploy.sh standard

# Check status:
./scripts/deploy.sh status
```

## Step 5: First login

```
URL:      http://your-server-ip:8000/auth/login
Username: admin
Password: Admin@2026   ← CHANGE THIS IMMEDIATELY
```

## Step 6: Change admin password

1. Login → Profile → Change Password
2. Create real staff accounts via Admin Dashboard → User Management
3. Assign correct roles and departments

## Step 7: HTTPS (production)

```bash
# Get SSL certificate (replaces http:// with https://)
./scripts/deploy.sh ssl-init nexus.yourhospital.rw admin@yourhospital.rw

# Switch to full profile (Nginx + HTTPS)
./scripts/deploy.sh full
```

## Step 8: Setup automated backups

```bash
# Add to crontab (backup at 2 AM daily)
crontab -e
# Add this line:
0 2 * * * /opt/nexus/scripts/backup.sh >> /var/log/nexus_backup.log 2>&1
```

## Step 9: Configure hospital settings

1. Login as admin → Admin Dashboard → Configuration
2. Set hospital name, address, phone
3. Set country, timezone (Africa/Kigali for Rwanda)
4. Set default language (en/fr/rw)

## Step 10: Verification checklist

- [ ] Can log in with new admin password
- [ ] Dashboard loads with white/cyan theme
- [ ] Hematology page shows CBC form
- [ ] Records page shows 42 books
- [ ] Can create a test patient
- [ ] Can enter a CBC result
- [ ] Critical value flags work (enter Hgb = 5.0)
- [ ] AI interpretation shows (if Ollama running)
- [ ] SMS test works (if Africa's Talking configured)
- [ ] Backup script runs (./scripts/backup.sh)
- [ ] HTTPS works (after SSL setup)

## Maintenance

```bash
# View logs
./scripts/deploy.sh logs api
./scripts/deploy.sh logs postgres

# Update to new version
./scripts/deploy.sh update

# Manual backup
./scripts/deploy.sh backup

# Full status
./scripts/deploy.sh status
```

## Emergency procedures

```bash
# Database restore from backup
gunzip -c /opt/nexus/backups/alis_x_20260101_020000.sql.gz | \
    docker compose exec -T postgres psql -U alis_x_user alis_x

# Restart specific service
docker compose restart api

# Stop everything
./scripts/deploy.sh stop
```
