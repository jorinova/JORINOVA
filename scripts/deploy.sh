#!/bin/bash
# ════════════════════════════════════════════════════════════════════════════
# JORINOVA NEXUS ALIS-X — Production Deployment Script
# ════════════════════════════════════════════════════════════════════════════
# Usage:
#   ./scripts/deploy.sh standard    → PostgreSQL + FastAPI + Ollama AI
#   ./scripts/deploy.sh full        → + Nginx HTTPS + Celery + Monitoring
#   ./scripts/deploy.sh offline     → PostgreSQL + FastAPI only (no AI)
#   ./scripts/deploy.sh update      → Pull + rebuild, zero-downtime restart
#   ./scripts/deploy.sh status      → Show service status
#   ./scripts/deploy.sh logs [svc]  → Tail logs (all or specific service)
#   ./scripts/deploy.sh backup      → Manual backup now
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

NEXUS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE="${1:-standard}"
ENV_FILE="${NEXUS_DIR}/backend/.env.production"
COMPOSE="docker compose -f ${NEXUS_DIR}/docker-compose.yml"

RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[1;33m' CYAN='\033[0;36m' NC='\033[0m'
info()  { echo -e "${CYAN}[NEXUS]${NC} $*"; }
ok()    { echo -e "${GREEN}[  OK ]${NC} $*"; }
warn()  { echo -e "${YELLOW}[ WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Pre-flight checks ─────────────────────────────────────────────────────────
preflight() {
    info "Pre-flight checks…"

    command -v docker &>/dev/null || error "Docker not installed."
    docker info &>/dev/null       || error "Docker daemon not running."
    docker compose version &>/dev/null || error "Docker Compose v2 not installed."

    [[ -f "${ENV_FILE}" ]] || error "Missing ${ENV_FILE}. Copy .env.production.example and fill in secrets."

    # Check for default secrets
    if grep -q "REPLACE_WITH" "${ENV_FILE}" 2>/dev/null; then
        error "Default secrets found in ${ENV_FILE}. Run: python scripts/generate_secrets.py"
    fi

    ok "Pre-flight: all checks passed."
}

# ── Deploy ────────────────────────────────────────────────────────────────────
deploy() {
    local profile="${1}"
    info "Deploying profile: ${profile}"

    # Build images
    info "Building Docker images…"
    ${COMPOSE} --profile "${profile}" build --no-cache

    # Start in order: database → migrate → api → ai → proxy
    info "Starting services (profile: ${profile})…"
    ${COMPOSE} --profile "${profile}" up -d --remove-orphans

    # Wait for API health
    info "Waiting for API health check…"
    local attempts=0
    until curl -sf http://localhost:8000/api/v1/health &>/dev/null; do
        attempts=$((attempts + 1))
        [[ ${attempts} -ge 30 ]] && error "API did not become healthy in 90s. Check logs."
        sleep 3
    done

    ok "API healthy ✓"
    ${COMPOSE} --profile "${profile}" ps

    info "Deployment complete."
    info "Admin login: http://localhost:8000/auth/login"
    info "Swagger API: http://localhost:8000/api/docs (internal only)"
}

# ── Zero-downtime update ──────────────────────────────────────────────────────
update() {
    info "Updating JORINOVA NEXUS ALIS-X…"
    git -C "${NEXUS_DIR}" pull --ff-only 2>/dev/null || warn "Git pull failed (manual update?)"

    info "Rebuilding API image…"
    ${COMPOSE} --profile "${PROFILE}" build api

    info "Rolling restart (zero downtime)…"
    ${COMPOSE} --profile "${PROFILE}" up -d --no-deps api

    ok "Update complete."
}

# ── Status ────────────────────────────────────────────────────────────────────
status() {
    echo ""
    info "=== JORINOVA NEXUS ALIS-X — Service Status ==="
    ${COMPOSE} ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
    echo ""

    # API health
    if curl -sf http://localhost:8000/api/v1/health &>/dev/null; then
        health=$(curl -s http://localhost:8000/api/v1/health)
        ok "API: $(echo $health | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["app"]+" v"+d["version"])' 2>/dev/null || echo 'online')"
    else
        warn "API: not responding"
    fi

    # Database
    if ${COMPOSE} exec -T postgres pg_isready -U "${DB_USER:-alis_x_user}" &>/dev/null 2>&1; then
        ok "PostgreSQL: ready"
    else
        warn "PostgreSQL: not ready"
    fi

    # Disk space
    info "Disk: $(df -h "${NEXUS_DIR}" | tail -1 | awk '{print $3"/"$2" used ("$5")"}')"
    info "Backups: $(ls "${NEXUS_DIR}/../backups/"*.sql.gz 2>/dev/null | wc -l) files"
}

# ── Logs ─────────────────────────────────────────────────────────────────────
logs() {
    local service="${2:-}"
    if [[ -n "${service}" ]]; then
        ${COMPOSE} logs -f --tail=100 "alis_${service}"
    else
        ${COMPOSE} logs -f --tail=50
    fi
}

# ── SSL setup (first time only) ───────────────────────────────────────────────
ssl_init() {
    local domain="${2:-}"
    local email="${3:-}"
    [[ -z "${domain}" ]] && error "Usage: deploy.sh ssl-init domain.rw admin@domain.rw"
    [[ -z "${email}" ]]  && error "Usage: deploy.sh ssl-init domain.rw admin@domain.rw"
    info "Obtaining SSL certificate for ${domain}…"
    docker run --rm \
        -v certbot_certs:/etc/letsencrypt \
        -v certbot_www:/var/www/certbot \
        certbot/certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        -d "${domain}" \
        -d "www.${domain}" \
        --email "${email}" \
        --agree-tos \
        --non-interactive
    ok "SSL certificate obtained for ${domain}"
    info "Now run: ./scripts/deploy.sh full"
}

# ── Main ──────────────────────────────────────────────────────────────────────
case "${PROFILE}" in
    standard|full|offline)
        preflight
        deploy "${PROFILE}"
        ;;
    update)
        update
        ;;
    status)
        status
        ;;
    logs)
        logs "$@"
        ;;
    backup)
        bash "${NEXUS_DIR}/scripts/backup.sh"
        ;;
    ssl-init)
        ssl_init "$@"
        ;;
    stop)
        info "Stopping all NEXUS services…"
        ${COMPOSE} --profile standard --profile full --profile offline down
        ok "All services stopped."
        ;;
    *)
        echo "Usage: $0 {standard|full|offline|update|status|logs [svc]|backup|stop|ssl-init domain email}"
        exit 1
        ;;
esac
