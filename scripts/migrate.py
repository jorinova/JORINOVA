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

# Centralized deterministic bootstrap (must run before DB/seed/random generation)
try:
    from core.bootstrap import initialize_application
    initialize_application()
except Exception as _e:
    # Fallback: keep old behavior; bootstrapping will still try to seed/migrate
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
    )
    log = logging.getLogger('migrate')
    log.warning('Determinism/ORM bootstrap failed, continuing: %s', str(_e)[:160])


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
)
log = logging.getLogger('migrate')



def run_migration(check_only: bool = False, seed_only: bool = False):
    from core.database import engine, create_all_tables, SessionLocal
    from core.config import get_settings
    from sqlalchemy import text, inspect
    from sqlalchemy.orm import configure_mappers

    settings = get_settings()
    log.info('Database URL: %s', settings.database_url[:50] + '…')
    log.info('Mode: %s', 'check' if check_only else ('seed-only' if seed_only else 'full migration'))

    # Ensure ALL ORM models are imported before mapper configuration
    # (fixes relationship string targets like 'Patient' not being resolvable).
    import models  # noqa: F401
    configure_mappers()

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


# ── Local seed helpers (mirror main.py so migrate.py is self-contained) ─────────

def _seed_inventory(db, hospital):
    """Seed essential lab inventory items — identical to main.py."""
    from models.inventory import InventoryItem
    from datetime import date
    items = [
        InventoryItem(item_code='EDTA-4ML',   name='EDTA 4mL Lavender Tubes',          category='consumable', unit='box/100', quantity=12, min_stock=5,  unit_cost=8500,  lot_number='L2026A', expiry_date=date(2027,3,1),  location='Store A',   hospital_id=hospital.id),
        InventoryItem(item_code='SST-5ML',    name='SST Gold Top 5mL Tubes',           category='consumable', unit='box/100', quantity=8,  min_stock=10, unit_cost=12000, lot_number='L2026B', expiry_date=date(2027,6,1),  location='Store A',   hospital_id=hospital.id),
        InventoryItem(item_code='CITRATE-3ML',name='Citrate 3mL Blue Tubes',           category='consumable', unit='box/100', quantity=6,  min_stock=5,  unit_cost=9000,  lot_number='L2026C', expiry_date=date(2027,4,1),  location='Store A',   hospital_id=hospital.id),
        InventoryItem(item_code='FLUOR-2ML',  name='Fluoride/Oxalate 2mL Grey Tubes',  category='consumable', unit='box/100', quantity=10, min_stock=5,  unit_cost=7500,  expiry_date=date(2027,6,1),  location='Store A',   hospital_id=hospital.id),
        InventoryItem(item_code='CHEM-GLUC',  name='Glucose Reagent (Cobas)',          category='reagent',    unit='cassette',quantity=4,  min_stock=3,  unit_cost=45000, lot_number='RG2026',  expiry_date=date(2026,8,15), location='Cold Room', hospital_id=hospital.id),
        InventoryItem(item_code='CHEM-CREAT', name='Creatinine Reagent',               category='reagent',    unit='cartridge',quantity=6, min_stock=3,  unit_cost=38000, expiry_date=date(2026,9,1),  location='Cold Room', hospital_id=hospital.id),
        InventoryItem(item_code='CHEM-LFT',   name='Liver Function Test Pack',         category='reagent',    unit='pack',    quantity=3,  min_stock=2,  unit_cost=95000, expiry_date=date(2026,10,1), location='Cold Room', hospital_id=hospital.id),
        InventoryItem(item_code='MAL-RDT',    name='Malaria RDT (HRP2/pLDH)',          category='reagent',    unit='box/25',  quantity=15, min_stock=5,  unit_cost=18000, lot_number='MAL2026', expiry_date=date(2026,12,1), location='Store B',   hospital_id=hospital.id),
        InventoryItem(item_code='HIV-COMBO',  name='HIV Ag/Ab Combo 4th Gen',          category='reagent',    unit='box/25',  quantity=22, min_stock=10, unit_cost=25000, expiry_date=date(2027,1,1),  location='Cold Room', hospital_id=hospital.id),
        InventoryItem(item_code='HBSAG-RDT',  name='HBsAg Rapid Test',                category='reagent',    unit='box/25',  quantity=18, min_stock=8,  unit_cost=15000, expiry_date=date(2026,11,1), location='Store B',   hospital_id=hospital.id),
        InventoryItem(item_code='BACTEC-AER', name='BACTEC Aerobic Blood Culture Bottles', category='reagent',unit='bottle', quantity=30, min_stock=20, unit_cost=4500,  expiry_date=date(2026,10,1), location='Cold Room', hospital_id=hospital.id),
        InventoryItem(item_code='GX-CRTG',    name='GeneXpert MTB/RIF Ultra Cartridges',category='reagent',  unit='cartridge',quantity=2, min_stock=5,  unit_cost=25000, expiry_date=date(2026,9,1),  location='Molecular', hospital_id=hospital.id),
        InventoryItem(item_code='GLOVES-M',   name='Latex Gloves Medium',             category='ppe',        unit='box/100', quantity=25, min_stock=10, unit_cost=3500,  location='PPE Store',         hospital_id=hospital.id),
        InventoryItem(item_code='GLOVES-L',   name='Latex Gloves Large',              category='ppe',        unit='box/100', quantity=18, min_stock=10, unit_cost=3500,  location='PPE Store',         hospital_id=hospital.id),
        InventoryItem(item_code='MASK-N95',   name='N95 Respirator Masks',            category='ppe',        unit='box/20',  quantity=8,  min_stock=5,  unit_cost=12000, expiry_date=date(2028,1,1),  location='PPE Store',         hospital_id=hospital.id),
        InventoryItem(item_code='SLIDE-PLAIN',name='Plain Glass Slides',              category='consumable', unit='box/72',  quantity=20, min_stock=5,  unit_cost=4500,  location='Store A',           hospital_id=hospital.id),
        InventoryItem(item_code='IMMERSION',  name='Immersion Oil (Type A)',          category='reagent',    unit='bottle',  quantity=5,  min_stock=2,  unit_cost=8000,  expiry_date=date(2028,6,1),  location='Microscopy', hospital_id=hospital.id),
        InventoryItem(item_code='LANCETS',    name='Safety Lancets 21G',              category='consumable', unit='box/200', quantity=12, min_stock=5,  unit_cost=6000,  expiry_date=date(2028,1,1),  location='Store A',   hospital_id=hospital.id),
    ]
    for it in items:
        db.add(it)
    db.commit()
    log.info('Inventory seeded: %d items', len(items))


_STAFF_SEED = [
    ('admin',        'admin123',  'super_admin',   'System',  'Administrator','admin@nexus.rw'),
    ('labmanager',   'nexus2026', 'lab_manager',   'Jean',    'Mutabazi',    'jm@nexus.rw'),
    ('scientist',    'nexus2026', 'scientist',     'Marie',   'Uwimana',     'mu@nexus.rw'),
    ('hematologist', 'nexus2026', 'scientist',     'Patrick', 'Nkurunziza',  'pn@nexus.rw'),
    ('biochemist',   'nexus2026', 'scientist',     'Alice',   'Mukamana',    'am@nexus.rw'),
    ('receptionist', 'nexus2026', 'receptionist',  'Grace',   'Ingabire',    'gi@nexus.rw'),
    ('pathologist',  'nexus2026', 'pathologist',   'Paul',    'Habimana',    'ph@nexus.rw'),
]


def _seed_staff(db, hospital, hash_fn):
    """Seed the standard 7-user staff roster."""
    from models.user import User
    added = 0
    for username, password, role, fn, ln, email in _STAFF_SEED:
        # Always skip admin — created by caller
        if username == 'admin':
            continue
        if db.query(User).filter(User.username == username).first():
            continue
        user = User(username=username, hashed_password=hash_fn(password),
                    role=role, first_name=fn, last_name=ln, email=email,
                    is_active=True, hospital_id=hospital.id)
        db.add(user)
        added += 1
    db.commit()
    log.info('Staff seeded: %d additional users', added)


# ── Universal Operators ─────────────────────────────────────────────────────────

_UNIVERSAL_OPERATOR_SEED = [
    # Lab-side
    ('LAB_TECH',       'Lab Tech R.','Lab Technician',      ['LAB_TECH'],              'lab@nexus.rw',   '+250788001001', 8.0, '06:00', '14:00'),
    ('LAB_TECH_2',     'Lab Tech M.','Lab Technician',      ['LAB_TECH'],              'lm@nexus.rw',    '+250788001002', 8.0, '14:00', '22:00'),
    ('PATHOLOGIST',    'Dr. P.','Pathologist',             ['PATHOLOGIST'],           'path@nexus.rw',  '+250788002001', 8.0, '08:00', '16:00'),
    ('QC_OFFICER',     'Q.C. Ofc.', 'QC Officer',          ['QC_OFFICER'],            'qc@nexus.rw',    '+250788003001', 8.0, '07:00', '15:00'),
    ('DATA_STEWARD',   'Data S.','Data Steward',           ['DATA_STEWARD'],          'dss@nexus.rw',   '+250788004001', 8.0, '08:00', '16:00'),
    ('RESULT_COORD',   'Res. Cord.','Result Coordinator', ['RESULT_COORD'],          'rc@nexus.rw',    '+250788005001', 8.0, '07:00', '15:00'),
    ('COURIER',        'Cour. J.', 'Courier',             ['COURIER'],               'courier@nexus.rw', '+250788006001', 8.0,'00:00', '23:59'),
    # Clinical
    ('UNIT_DOCTOR',    'Dr. U.','Unit Doctor',             ['UNIT_DOCTOR'],           'ud@nexus.rw',    '+250788007001', 8.0, '08:00', '16:00'),
    ('NURSE',          'Nurse A.', 'Nurse',               ['NURSE'],                 'nurse@nexus.rw', '+250788008001', 8.0, '06:00', '14:00'),
    ('CLINICIAN',      'Clin. B.', 'Clinician',            ['CLINICIAN'],             'clin@nexus.rw',  '+250788009001', 8.0, '09:00', '17:00'),
    ('GYNAECOLOGIST',  'Dr. G.',   'Gynaecologist',         ['GYNAECOLOGIST'],         'gyn@nexus.rw',   '+250788010001', 8.0, '09:00', '17:00'),
    ('ONCOLOGIST',     'Dr. O.',   'Oncologist',            ['ONCOLOGIST'],            'onco@nexus.rw',  '+250788011001', 8.0, '09:00', '17:00'),
    ('RADIOLOGIST',    'Dr. R.',   'Radiologist',           ['RADIOLOGIST'],           'rad@nexus.rw',   '+250788012001', 8.0, '08:00', '16:00'),
]


def _seed_universal_operators(db, hash_fn):
    """Seed the 12 universal operator roles — always fill all 12 before stopping."""
    import json
    from models.universal import UniversalOperator, DepartmentOperator
    from models.core_config import LaboratoryDepartment

    added = 0
    for row in _UNIVERSAL_OPERATOR_SEED:
        short, full, role_type, roles, email, phone, hrs, s_start, s_end = row
        if db.query(UniversalOperator).filter(UniversalOperator.short_name == short).first():
            continue
        op = UniversalOperator(
            short_name=short, full_name=full, role_type=role_type,
            roles=json.dumps(roles), email=email, phone=phone,
            default_hours_per_day=hrs, shift_start=s_start, shift_end=s_end,
            is_active=True,
        )
        db.add(op)
        added += 1
    db.commit()

    # Assign each operator to all active departments
    depts = db.query(LaboratoryDepartment).filter(LaboratoryDepartment.is_active == True).all()
    if depts:
        ops = db.query(UniversalOperator).all()
        links = 0
        for op in ops:
            for dept in depts:
                exists = db.query(DepartmentOperator).filter(
                    DepartmentOperator.operator_id == op.id,
                    DepartmentOperator.department_id == dept.id,
                ).first()
                if not exists:
                    db.add(DepartmentOperator(operator_id=op.id, department_id=dept.id))
                    links += 1
        db.commit()
        log.info('Universal operators seeded: %d | dept-links created: %d', added, links)
    else:
        log.info('Universal operators seeded: %d (no departments available for linking)', added)


def _seed_24h_counters(db, hospital):
    """Seed one Daily24hRackCounter row per active department for today."""
    from datetime import date
    from models.worklist import Daily24hRackCounter
    from models.core_config import LaboratoryDepartment

    today = date.today()
    depts = db.query(LaboratoryDepartment).filter(LaboratoryDepartment.is_active == True).all()
    added = 0
    for dept in depts:
        exists = db.query(Daily24hRackCounter).filter(
            Daily24hRackCounter.department == dept.code,
            Daily24hRackCounter.counter_date == today,
        ).first()
        if exists:
            continue
        db.add(Daily24hRackCounter(
            department=dept.code, counter_date=today, last_number=0,
        ))
        added += 1
    db.commit()
    log.info('24h rack counters seeded: %d departments for %s', added, today)




def _seed(settings):
    """Seed default hospital, admin user, test catalog, specimen types,
    and inventory — aligned with FastAPI startup seed for consistency."""
    from core.database import SessionLocal
    from core.security import hash_password
    from services.worklist_service import seed_specimen_types

    db = SessionLocal()
    try:
        from models.core_config import Hospital
        from models.user import User

        # Default hospital (consistent name across migrate.py and FastAPI startup)
        hospital = db.query(Hospital).first()
        if not hospital:
            hospital = Hospital(
                name='JORINOVA NEXUS Default Hospital',
                address='Rwanda', district='Kigali', phone='+250000000000',
                hospital_type='public', has_lab=True,
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
                username='admin', email='admin@alis-x.rw',
                first_name='ALIS-X', last_name='Admin',
                hashed_password=hash_password('Admin@2026'),
                role='super_admin', is_superuser=True, is_active=True,
                hospital_id=hospital.id,
            )
            db.add(admin)
            log.warning('Admin user created — CHANGE PASSWORD IMMEDIATELY: admin / Admin@2026')
        else:
            log.info('Admin user exists: %s', admin.username)

        db.commit()

        # Specimen types (worklist)
        seeded = seed_specimen_types(db)
        if seeded:
            log.info('Specimen types seeded: %d', seeded)

        # Test catalog
        from models.core_config import TestCatalog
        if db.query(TestCatalog).count() == 0:
            log.info('Loading test catalog…')
            import asyncio
            from services.test_rules_loader import load_test_rules
            asyncio.run(load_test_rules(db, hospital))
            log.info('Test catalog loaded.')
        else:
            log.info('Test catalog: %d tests already loaded', db.query(TestCatalog).count())

        # Inventory (essential lab supplies)
        from models.inventory import InventoryItem
        if db.query(InventoryItem).count() == 0:
            _seed_inventory(db, hospital)

        # Seed a minimal staff roster if empty beyond admin
        from models.user import User
        if db.query(User).count() == 1:
            _seed_staff(db, hospital, hash_password)

        # Universal operators (all 12 roles)
        _seed_universal_operators(db, hash_password)

        # 24h cross-shift rack counter rows (one per department per day)
        _seed_24h_counters(db, hospital)

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
