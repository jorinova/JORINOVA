# ══════════════════════════════════════════════════════════════════════════════
# JORINOVA NEXUS ALIS-X — Frontend (Next.js) production image
# ══════════════════════════════════════════════════════════════════════════════
# Three stages, ~280 MB final image:
#   1. deps    — install npm dependencies
#   2. build   — compile Next.js with `output: 'standalone'`
#   3. runner  — minimal node:alpine running the compiled app
#
# Build:
#   docker build -t jorinova/web:latest ./frontend
# Run (smoke test):
#   docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://api:8000 jorinova/web:latest
# ══════════════════════════════════════════════════════════════════════════════

# ── Stage 1: install deps ─────────────────────────────────────────────────────
FROM node:24-alpine AS deps
WORKDIR /app

# Only copy lock + manifest for max layer-cache hit rate
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund


# ── Stage 2: build ────────────────────────────────────────────────────────────
FROM node:24-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build-time public env. Nginx will reverse-proxy /api → backend; the
# browser uses the relative /api path, so NEXT_PUBLIC_API_URL is empty
# by default. Pass --build-arg NEXT_PUBLIC_API_URL=... if you need an
# absolute origin (e.g. mobile app or external CDN).
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build


# ── Stage 3: runner ───────────────────────────────────────────────────────────
FROM node:24-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Run as a non-root user. Alpine ships with the 'node' user (uid 1000).
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Standalone output bundles only the files needed to run the server.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static     ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public           ./public

USER nextjs
EXPOSE 3000

# Healthcheck the dashboard route (renders even with no API reachable
# because RequireAuth short-circuits when no token is present).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:3000/login || exit 1

CMD ["node", "server.js"]
