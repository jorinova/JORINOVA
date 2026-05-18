-- ══════════════════════════════════════════════════════════════════════════
-- JORINOVA NEXUS ALIS-X — PostgreSQL initialisation
-- Runs once when the PostgreSQL container is first created.
-- ══════════════════════════════════════════════════════════════════════════

-- Extensions for medical data
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";     -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";       -- Fast text search (patient names)
CREATE EXTENSION IF NOT EXISTS "unaccent";      -- French/Kinyarwanda accent-insensitive search
CREATE EXTENSION IF NOT EXISTS "btree_gin";     -- Composite index support

-- Enforce UTF-8
SET client_encoding = 'UTF8';

-- ── Performance settings (tuned for hospital LIS workload) ────────────────
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '768MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET random_page_cost = 1.1;         -- Assume SSD
ALTER SYSTEM SET effective_io_concurrency = 200;  -- SSD concurrent I/O
ALTER SYSTEM SET max_connections = 100;
ALTER SYSTEM SET work_mem = '4MB';

-- ── Audit: prevent row deletion on critical tables (DB trigger level) ──────
-- These are reinforced at application layer but defence-in-depth here.
-- Audit logs and critical books cannot be physically deleted.
-- (Triggers added after table creation by Alembic migration)
