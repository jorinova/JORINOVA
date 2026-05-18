"""
SQLite → PostgreSQL Data Migration
====================================
Copies ALL data from the existing SQLite database into PostgreSQL.
Run this ONCE when switching from SQLite to PostgreSQL.

Usage:
  1. Start PostgreSQL (docker compose --profile offline up -d postgres)
  2. Run tables migration: python scripts/migrate.py
  3. Run this script:     python scripts/migrate_sqlite_to_postgres.py
  4. Verify:              python scripts/migrate_sqlite_to_postgres.py --verify

WARNING: This will REPLACE data in PostgreSQL with SQLite data.
         Only run this during initial migration, not ongoing operations.
"""
import sys, os, logging, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('sqlite_migrate')

# Tables to migrate in dependency order (parents before children)
TABLE_ORDER = [
    'hospitals', 'users', 'login_logs',
    'lab_departments', 'test_catalog', 'test_interpretation_rules', 'reflex_test_rules',
    'patients',
    'lab_requests', 'samples', 'lab_results', 'critical_result_book',
    'biochem_worklists', 'worklist_items', 'biochem_results', 'biochem_critical_book',
    'blood_units', 'donors', 'donation_events', 'crossmatch_results',
    'haemovigilance_events', 'inter_hospital_exchanges', 'blood_requests', 'temperature_logs',
    'storage_units', 'storage_chambers',
    'inventory_items', 'stock_transactions', 'stock_alerts',
    'billing', 'billing_items', 'test_consumables',
    'micro_cultures', 'antibiograms', 'parasitology_results', 'micro_critical_book',
    'pcr_results', 'viral_loads', 'genetic_analyses', 'molecular_critical_book',
    'hem_results', 'malaria_results', 'peripheral_smears',
    'coag_results', 'coag_iqc',
    'serology_results',
    'dipstick_results', 'urine_microscopy',
    'iqc_results', 'eqa_results', 'sops', 'ncr_records', 'capa_actions',
    'staff_profiles', 'shifts', 'shift_assignments', 'leave_requests', 'performance_marks',
    'surveillance_signals', 'disease_tracking',
    'notifications', 'sms_queue',
    'voice_settings',
    'escalation_records',
    'sample_rejections',
    'audit_logs',
]

# Tables to SKIP (immutable or auto-generated)
SKIP_TABLES = {'alembic_version'}


def migrate(dry_run: bool = False, verify_only: bool = False):
    from core.config import get_settings
    from sqlalchemy import create_engine, inspect, text, MetaData

    settings = get_settings()

    # SQLite source
    sqlite_path = Path(__file__).parent.parent / 'backend' / 'alis_x.db'
    if not sqlite_path.exists():
        log.error('SQLite database not found: %s', sqlite_path)
        sys.exit(1)

    sqlite_url = f'sqlite:///{sqlite_path}'
    pg_url = (f'postgresql+psycopg2://{settings.db_user}:{settings.db_password}'
              f'@{settings.db_host}:{settings.db_port}/{settings.db_name}')

    log.info('Source (SQLite): %s', sqlite_path)
    log.info('Target (PgSQL):  %s', pg_url[:50] + '…')

    sqlite_engine = create_engine(sqlite_url)
    pg_engine     = create_engine(pg_url)

    if verify_only:
        _verify(sqlite_engine, pg_engine)
        return

    sqlite_insp = inspect(sqlite_engine)
    pg_insp     = inspect(pg_engine)

    sqlite_tables = set(sqlite_insp.get_table_names())
    pg_tables     = set(pg_insp.get_table_names())

    log.info('SQLite tables: %d | PostgreSQL tables: %d', len(sqlite_tables), len(pg_tables))

    total_rows = 0
    failed     = []

    with sqlite_engine.connect() as src, pg_engine.begin() as dst:
        for table in TABLE_ORDER + sorted(sqlite_tables - set(TABLE_ORDER)):
            if table in SKIP_TABLES or table not in sqlite_tables:
                continue
            if table not in pg_tables:
                log.warning('Table not in PostgreSQL (skipping): %s', table)
                continue

            # Count source rows
            count = src.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
            if count == 0:
                log.info('  SKIP %s (empty)', table)
                continue

            log.info('  Migrating %s: %d rows…', table, count)
            if dry_run:
                total_rows += count
                continue

            try:
                # Fetch all rows from SQLite
                rows = src.execute(text(f'SELECT * FROM "{table}"')).fetchall()
                keys = src.execute(text(f'SELECT * FROM "{table}" LIMIT 0')).keys()
                col_names = list(keys)

                # Disable triggers/constraints temporarily for import
                dst.execute(text(f'ALTER TABLE "{table}" DISABLE TRIGGER ALL'))

                # Clear existing data in PostgreSQL
                dst.execute(text(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE'))

                # Insert in batches of 500
                batch_size = 500
                for i in range(0, len(rows), batch_size):
                    batch = rows[i:i+batch_size]
                    dicts = [dict(zip(col_names, row)) for row in batch]
                    dst.execute(
                        text(f'INSERT INTO "{table}" ({", ".join(f\'"{c}"\' for c in col_names)}) '
                             f'VALUES ({", ".join(f":{c}" for c in col_names)})'),
                        dicts
                    )

                # Re-enable triggers
                dst.execute(text(f'ALTER TABLE "{table}" ENABLE TRIGGER ALL'))

                # Reset sequences
                for col in col_names:
                    if col == 'id':
                        dst.execute(text(
                            f"SELECT setval(pg_get_serial_sequence('\"{table}\"', 'id'), "
                            f"COALESCE(MAX(id), 0) + 1) FROM \"{table}\""
                        ))
                        break

                total_rows += count
                log.info('    ✓ %s: %d rows migrated', table, count)

            except Exception as e:
                log.error('    ✗ %s FAILED: %s', table, e)
                failed.append((table, str(e)))

    log.info('='*60)
    log.info('Migration %s', 'DRY RUN' if dry_run else 'COMPLETE')
    log.info('Total rows: %d', total_rows)
    if failed:
        log.error('FAILED tables (%d):', len(failed))
        for t, err in failed: log.error('  %s: %s', t, err)
    else:
        log.info('All tables migrated successfully ✓')

    return len(failed) == 0


def _verify(sqlite_engine, pg_engine):
    from sqlalchemy import text, inspect
    log.info('Verifying migration…')
    sq_insp = inspect(sqlite_engine)
    pg_insp = inspect(pg_engine)

    with sqlite_engine.connect() as src, pg_engine.connect() as dst:
        all_match = True
        for table in sq_insp.get_table_names():
            if table in SKIP_TABLES: continue
            try:
                sq_count = src.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
                pg_count = dst.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
                match = sq_count == pg_count
                log.info('  %s %s: SQLite=%d PgSQL=%d', '✓' if match else '✗', table, sq_count, pg_count)
                if not match: all_match = False
            except Exception as e:
                log.warning('  ? %s: %s', table, e)
    log.info('Verification: %s', 'PASSED ✓' if all_match else 'FAILED ✗')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SQLite → PostgreSQL migration')
    parser.add_argument('--dry-run',     action='store_true', help='Count rows only, no insert')
    parser.add_argument('--verify',      action='store_true', help='Verify migration counts')
    args = parser.parse_args()

    success = migrate(dry_run=args.dry_run, verify_only=args.verify)
    sys.exit(0 if success else 1)
