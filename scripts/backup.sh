#!/bin/bash
# ════════════════════════════════════════════════════════════════════════════
# JORINOVA NEXUS ALIS-X — Automated Database Backup
# ════════════════════════════════════════════════════════════════════════════
# Cron (daily at 2:00 AM):
#   0 2 * * * /opt/nexus/scripts/backup.sh >> /var/log/nexus_backup.log 2>&1
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

BACKUP_DIR="/opt/nexus/backups"
RETAIN_DAYS=30
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/alis_x_${TIMESTAMP}.sql.gz"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

# Load env
source /opt/nexus/backend/.env.production 2>/dev/null || true
DB_NAME="${DB_NAME:-alis_x}"
DB_USER="${DB_USER:-alis_x_user}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

echo "[$(date)] Starting backup → ${BACKUP_FILE}"
mkdir -p "${BACKUP_DIR}"

# Dump PostgreSQL
PGPASSWORD="${DB_PASSWORD}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --format=plain \
    --no-owner \
    --no-acl \
    --encoding=UTF8 \
| gzip > "${BACKUP_FILE}"

# Generate checksum for integrity verification
sha256sum "${BACKUP_FILE}" > "${CHECKSUM_FILE}"

FILE_SIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)
echo "[$(date)] Backup complete: ${BACKUP_FILE} (${FILE_SIZE})"

# Also backup media files (staff photos, uploaded documents)
MEDIA_BACKUP="${BACKUP_DIR}/media_${TIMESTAMP}.tar.gz"
tar -czf "${MEDIA_BACKUP}" -C /opt/nexus media/ 2>/dev/null || true
echo "[$(date)] Media backup: ${MEDIA_BACKUP}"

# Remove old backups (keep RETAIN_DAYS days)
find "${BACKUP_DIR}" -name "alis_x_*.sql.gz"   -mtime "+${RETAIN_DAYS}" -delete
find "${BACKUP_DIR}" -name "media_*.tar.gz"     -mtime "+${RETAIN_DAYS}" -delete
find "${BACKUP_DIR}" -name "*.sha256"           -mtime "+${RETAIN_DAYS}" -delete

REMAINING=$(find "${BACKUP_DIR}" -name "alis_x_*.sql.gz" | wc -l)
echo "[$(date)] Cleanup done. ${REMAINING} backups retained (${RETAIN_DAYS}d policy)."

# Optional: copy to remote (uncomment and configure)
# rsync -az "${BACKUP_FILE}" user@remote-server:/backups/nexus/
# aws s3 cp "${BACKUP_FILE}" s3://nexus-backups/$(date +%Y/%m/)/

echo "[$(date)] Backup SUCCESSFUL ✓"
