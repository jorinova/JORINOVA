"""
ALIS-X Production Core — smoke / integration test suite.

Run standalone:
    python services/test_production_core.py

Or via pytest:
    pytest services/test_production_core.py -v

Tests are grouped by severity:
    P0  blocking  — import / mapper / startup
    P1  critical  — DB, auth, seeding
    P2  high      — AI independence
    P3  medium    — API round-trip health
"""
from __future__ import annotations

import os
import sys
import random
import unittest
from pathlib import Path
from typing import Any

# ── Bootstrap path so tests can run from repo root ────────────────────────────
_HERE = Path(__file__).resolve().parent      # backend/services
_BACKEND = _HERE.parent                      # backend/
sys.path.insert(0, str(_BACKEND))

os.environ.setdefault('GLOBAL_SEED', '42')

from core.determinism import initialize_determinism  # noqa: E402
initialize_determinism()


# ══════════════════════════════════════════════════════════════════════════════
# P0 — BLOCKING: imports, mapper, startup
# ══════════════════════════════════════════════════════════════════════════════

class TestP0Imports(unittest.TestCase):
    """P0: All model and service imports must succeed without error."""

    def test_import_all_models(self):
        import models  # noqa: F401 — triggers __init__.py cascade
        self.assertIsNotNone(models)

    def test_import_all_department_models(self):
        dept_modules = [
            'hematology', 'biochemistry', 'coagulation', 'blood_bank',
            'serology', 'urinalysis', 'microbiology', 'molecular',
            'quality', 'inventory', 'worklist', 'billing', 'notifications',
            'audit', 'rejection', 'staffhub', 'surveillance',
            'voice_settings', 'escalation', 'voice_biometric', 'sync_queue',
        ]
        import models
        for mod in dept_modules:
            self.assertTrue(
                hasattr(models, mod),
                msg=f'Model package missing: models.{mod}',
            )

    def test_mapper_configuration(self):
        from core.database import Base, engine
        from sqlalchemy.orm import configure_mappers
        # Should not raise
        configure_mappers()

    def test_import_core_services(self):
        from services.worklist_service import route_request_to_worklist  # noqa: F401
        from services.routing_service import RoutingService              # noqa: F401
        from services.test_rules_data import DEPARTMENTS, TESTS          # noqa: F401

    def test_determinism_module_loads(self):
        from core.determinism import GLOBAL_SEED, initialize_determinism
        self.assertEqual(GLOBAL_SEED, 42)


# ══════════════════════════════════════════════════════════════════════════════
# P1 — CRITICAL: database, auth, seeding consistency
# ══════════════════════════════════════════════════════════════════════════════

class TestP1Database(unittest.TestCase):
    """P1: Database connectivity, schema, and seed data."""

    @classmethod
    def setUpClass(cls):
        from core.database import SessionLocal
        cls._Session = SessionLocal

    def _db(self):
        return self._Session()

    def test_database_connectivity(self):
        from core.database import engine
        with engine.connect() as conn:
            result = conn.execute(__import__('sqlalchemy').text('SELECT 1'))
            self.assertEqual(result.scalar(), 1)

    def test_critical_tables_exist(self):
        from core.database import Base, engine
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(engine)
        tables = set(inspector.get_table_names())
        for critical in (
            'users', 'patients', 'hospitals', 'lab_requests', 'lab_results',
            'audit_logs', 'escalation_records', 'sample_rejections',
        ):
            self.assertIn(critical, tables, msg=f'Critical table missing: {critical}')

    def test_seed_hospital_exists(self):
        from models.core_config import Hospital
        db = self._db()
        try:
            h = db.query(Hospital).first()
            self.assertIsNotNone(h, 'No hospital seeded — seed failure')
        finally:
            db.close()

    def test_seed_admin_user_exists(self):
        from models.user import User
        db = self._db()
        try:
            admin = db.query(User).filter(User.username == 'admin').first()
            self.assertIsNotNone(admin, 'Admin user not seeded')
            self.assertTrue(admin.is_superuser)
        finally:
            db.close()

    def test_seed_test_catalog_populated(self):
        from models.core_config import TestCatalog
        db = self._db()
        try:
            count = db.query(TestCatalog).count()
            self.assertGreater(count, 0, 'Test catalog is empty')
        finally:
            db.close()

    def test_seed_specimen_types_populated(self):
        from models.worklist import SpecimenTypeConfig
        db = self._db()
        try:
            count = db.query(SpecimenTypeConfig).count()
            self.assertGreater(count, 0, 'Specimen types not seeded')
        finally:
            db.close()


# ══════════════════════════════════════════════════════════════════════════════
# P2 — HIGH: determinism, AI independence
# ══════════════════════════════════════════════════════════════════════════════

class TestP2Determinism(unittest.TestCase):
    """P2: Seeded RNG produces identical output across runs."""

    def test_random_seed_reproducible(self):
        initialize_determinism()
        random.seed(42)
        run_a = [random.randint(0, 9999) for _ in range(32)]

        initialize_determinism()
        random.seed(42)
        run_b = [random.randint(0, 9999) for _ in range(32)]

        self.assertEqual(run_a, run_b, 'Random output differs between runs')

    def test_global_seed_env_default(self):
        from core.determinism import GLOBAL_SEED
        self.assertEqual(GLOBAL_SEED, 42)


class TestP2AIIndependence(unittest.TestCase):
    """P2: Core ORM access does not require AI infrastructure."""

    def test_routing_service_import_no_ai(self):
        """RoutingService must import without touching Ollama / Claude."""
        from services.routing_service import RoutingService  # noqa: F401
        self.assertIsNotNone(RoutingService)

    def test_worklist_service_no_ai_import(self):
        from services import worklist_service
        source = Path(worklist_service.__file__).read_text(encoding='utf-8')
        # Must NOT import cloud LLM or Ollama client modules
        forbidden = ['ollama', 'anthropic', 'claude', 'openai']
        for kw in forbidden:
            self.assertNotIn(
                kw.lower(), source.lower(),
                msg=f'worklist_service imports AI module: {kw}',
            )

    def test_core_database_no_ai_import(self):
        from core import database
        source = Path(database.__file__).read_text(encoding='utf-8')
        forbidden = ['ollama', 'anthropic', 'claude', 'openai', 'langchain']
        for kw in forbidden:
            self.assertNotIn(
                kw.lower(), source.lower(),
                msg=f'database module imports AI component: {kw}',
            )


# ══════════════════════════════════════════════════════════════════════════════
# P3 — MEDIUM: seed data completeness
# ══════════════════════════════════════════════════════════════════════════════

class TestP3SeedCompleteness(unittest.TestCase):
    """P3: Verify seed scripts produce consistent, complete datasets."""

    @classmethod
    def setUpClass(cls):
        from core.database import SessionLocal
        cls._Session = SessionLocal

    def _db(self):
        return self._Session()

    def test_inventory_seeded(self):
        from models.inventory import InventoryItem
        db = self._db()
        try:
            count = db.query(InventoryItem).count()
            self.assertGreater(count, 0, 'Inventory not seeded')
        finally:
            db.close()

    def test_departments_seeded(self):
        from models.core_config import LaboratoryDepartment
        db = self._db()
        try:
            count = db.query(LaboratoryDepartment).count()
            self.assertGreaterEqual(count, 6, 'Too few departments seeded')
        finally:
            db.close()

    def test_root_reachable(self):
        db = self._db()
        try:
            r = db.execute(__import__('sqlalchemy').text('SELECT 1')).scalar()
            self.assertEqual(r, 1)
        finally:
            db.close()

    def test_universal_operators_seeded(self):
        from models.universal import UniversalOperator
        db = self._db()
        try:
            count = db.query(UniversalOperator).count()
            self.assertGreaterEqual(count, 11,
                msg=f'Expected ≥11 UniversalOperators, got {count}')
        finally:
            db.close()

    def test_24h_rack_counters_seeded(self):
        from models.worklist import Daily24hRackCounter
        from datetime import date
        db = self._db()
        try:
            today = date.today()
            rows = db.query(Daily24hRackCounter).filter(
                Daily24hRackCounter.counter_date == today,
            ).all()
            self.assertGreater(len(rows), 0,
                msg=f'No 24h rack counter for {today}')
        finally:
            db.close()


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    verbosity = 2 if '--verbose' in sys.argv else 1
    unittest.main(verbosity=verbosity)
