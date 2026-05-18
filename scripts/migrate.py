"""
JORINOVA NEXUS ALIS-X — Database Migration Script
===================================================
Runs on every deployment (idempotent).
  1. Creates all tables from SQLAlchemy models (create_all)
  2. Seeds default data (hospital, admin user, test catalog)
  3. Reports on migration status

Usage:
  python scripts/migrate.py                  # run migration
  python scripts/migrate.py --check          # check only, no changes
  python scripts/migrate.py --seed-only      # re-seed defaults only
"""
import sys
import os
import logging
import argparse

# Make sure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
)
log = logging.getLogger('migrate')


def run_migration(check_only: bool = False, seed_only: bool = False):
    from core.database import engine, create_all_tables, SessionLocal
    from core.config import get_settings
    from sqlalchemy import text, inspect

    settings = get_settings()
    log.info('Database URL: %s', settings.database_url[:50] + '…')
    log.info('Mode: %s', 'check' if check_only else ('seed-only' if seed_only else 'full migration'))

    if check_only:
        # Just verify connectivity
        with engine.connect() as conn:
            result = conn.execute(text('SELECT 1'))
            log.info('Database connection: OK (result=%s)', result.scalar())
        return True

    if not seed_only:
        log.info('Creating tables…')
        create_all_tables()

        # Verify tables exist
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        log.info('Tables created: %d total', len(tables))
        critical_tables = ['users', 'patients', 'hospitals', 'lab_requests', 'lab_results',
                          'audit_logs', 'escalation_records', 'sample_rejections']
        for t in critical_tables:
            exists = t in tables
            log.info('  %s %s', '✓' if exists else '✗', t)
            if not exists:
                log.error('CRITICAL TABLE MISSING: %s', t)
                return False

        # Add production database constraints
        _add_production_constraints()

    log.info('Seeding default data…')
    _seed(settings)
    log.info('Migration complete ✓')
    return True


def _add_production_constraints():
    """Add DB-level constraints that SQLAlchemy models don't enforce."""
    from core.database import engine
    from sqlalchemy import text

    constraints = [
        # Audit logs: immutable — no UPDATE or DELETE at DB level
        """
        DO $$ BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.triggers
            WHERE trigger_name = 'audit_logs_immutable'
          ) THEN
            CREATE OR REPLACE FUNCTION prevent_audit_modification()
            RETURNS TRIGGER AS $f$
            BEGIN
              RAISE EXCEPTION 'Audit logs are immutable. modification rejected.';
            END;
            $f$ LANGUAGE plpgsql;

            CREATE TRIGGER audit_logs_immutable
              BEFORE UPDATE OR DELETE ON audit_logs
              FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
          END IF;
        END $$;
        """,
        # Critical books: immutable
        """
        DO $$ BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.triggers
            WHERE trigger_name = 'micro_critical_immutable'
          ) THEN
            CREATE OR REPLACE FUNCTION prevent_critical_modification()
            RETURNS TRIGGER AS $f$
            BEGIN
              RAISE EXCEPTION 'Critical book entries are immutable.';
            END;
            $f$ LANGUAGE plpgsql;

            CREATE TRIGGER micro_critical_immutable
              BEFORE UPDATE OR DELETE ON micro_critical_book
              FOR EACH ROW EXECUTE FUNCTION prevent_critical_modification();

            CREATE TRIGGER mol_critical_immutable
              BEFORE UPDATE OR DELETE ON molecular_critical_book
              FOR EACH ROW EXECUTE FUNCTION prevent_critical_modification();
          END IF;
        END $$;
        """,
    ]

    with engine.begin() as conn:
        for sql in constraints:
            try:
                conn.execute(text(sql))
                log.info('Constraint applied: OK')
            except Exception as e:
                log.warning('Constraint skipped (may not apply to SQLite): %s', str(e)[:60])


def _seed(settings):
    """Seed default hospital, admin user, and test catalog."""
    from core.database import SessionLocal
    from core.security import hash_password

    db = SessionLocal()
    try:
        from models.core_config import Hospital, LaboratoryDepartment
        from models.user import User

        # Default hospital
        hospital = db.query(Hospital).first()
        if not hospital:
            hospital = Hospital(
                name=os.environ.get('HOSPITAL_NAME', 'JORINOVA NEXUS Hospital'),
                address='Rwanda',
                district='Kigali',
                phone='+250000000000',
                hospital_type='public',
                has_lab=True,
            )
            db.add(hospital)
            db.flush()
            log.info('Default hospital created: %s', hospital.name)
        else:
            log.info('Hospital exists: %s', hospital.name)

        # Admin user
        admin = db.query(User).filter(User.username == 'admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@alis-x.rw',
                first_name='ALIS-X',
                last_name='Admin',
                hashed_password=hash_password('Admin@2026'),
                role='super_admin',
                is_superuser=True,
                is_active=True,
                hospital_id=hospital.id,
            )
            db.add(admin)
            log.warning('Admin user created — CHANGE PASSWORD IMMEDIATELY: admin / Admin@2026')
        else:
            log.info('Admin user exists: %s', admin.username)

        db.commit()

        # Test catalog
        from models.core_config import TestCatalog
        if db.query(TestCatalog).count() == 0:
            log.info('Loading test catalog…')
            import asyncio
            from main import _load_test_rules
            asyncio.run(_load_test_rules(db, hospital))
            log.info('Test catalog loaded.')
        else:
            log.info('Test catalog: %d tests already loaded', db.query(TestCatalog).count())

    except Exception as e:
        db.rollback()
        log.error('Seed error: %s', e)
        raise
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ALIS-X Database Migration')
    parser.add_argument('--check',     action='store_true', help='Check connectivity only')
    parser.add_argument('--seed-only', action='store_true', help='Re-seed defaults only')
    args = parser.parse_args()

    success = run_migration(check_only=args.check, seed_only=args.seed_only)
    sys.exit(0 if success else 1)
