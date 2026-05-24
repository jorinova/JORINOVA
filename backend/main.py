"""
JORINOVA NEXUS ALIS-X — FastAPI Application
Version 2.0 | FastAPI + SQLAlchemy + Hybrid AI (Local + Cloud)
"""
import os
import re
import sys
import logging
from contextlib import asynccontextmanager
from datetime import date as date_today, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, status, Cookie
from fastapi import WebSocket, WebSocketDisconnect

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import BaseLoader, Environment, FileSystemLoader, TemplateNotFound

# ── Ensure backend is on sys.path ──────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from core.config import get_settings
from core.database import create_all_tables
from core.security import hash_password

# Centralized deterministic bootstrap (must run before any demo/seed/random generation)
try:
    from core.bootstrap import initialize_application

    # Enforce Python 3.12-only runtime compatibility
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError(
            f"ALIS-X requires Python 3.12.x only. Current interpreter: {sys.version}"
        )

    initialize_application()

except Exception as _e:
    logging.getLogger('alis_x').warning('Determinism/ORM bootstrap failed, continuing: %s', str(_e)[:160])

logging.basicConfig(
    level=logging.INFO,

    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
)
logger   = logging.getLogger('alis_x')
settings = get_settings()

# ── Django → Jinja2 template preprocessor ────────────────────────────────────

_DATE_FMT_MAP = {
    'l, d F Y': '%A, %d %B %Y',
    'D, d M Y': '%a, %d %b %Y',
    'Y-m-d':    '%Y-%m-%d',
    'd/m/Y':    '%d/%m/%Y',
    'Y':        '%Y',
    'l':        '%A',
    'H:i':      '%H:%M',
}


def _preprocess(source: str) -> str:
    """Convert Django template syntax to Jinja2-compatible syntax."""
    # 1. Remove {% load ... %}
    source = re.sub(r'\{%-?\s*load\s+[\w\s]+\s*-?%\}', '', source)

    # 2. {% static 'path' %} and {% static "path" %} → {{ static('path') }}
    source = re.sub(
        r"""\{%-?\s*static\s+['"](.*?)['"]\s*-?%\}""",
        r"{{ static('\1') }}", source,
    )

    # 3. Remove {% csrf_token %}
    source = re.sub(r'\{%-?\s*csrf_token\s*-?%\}',
                    '<input type="hidden" name="csrfmiddlewaretoken" value="nexus-token">', source)

    # 4. {{ var|date:"format" }} and {{ var|date:'format' }} → {{ var.strftime('fmt') }}
    def _date_sub(m):
        var, fmt = m.group(1).strip(), m.group(2)
        py_fmt = _DATE_FMT_MAP.get(fmt, '%d %b %Y')
        return '{{{{ {}.strftime("{}") }}}}'.format(var, py_fmt)
    source = re.sub(r'\{\{\s*([\w.]+)\|date:"([^"]+)"\s*\}\}', _date_sub, source)
    source = re.sub(r"\{\{\s*([\w.]+)\|date:'([^']+)'\s*\}\}", _date_sub, source)
    # Also inside expressions: today|date:"..." →  today.strftime("...")
    def _date_inline(m):
        var, fmt = m.group(1).strip(), m.group(2)
        py_fmt = _DATE_FMT_MAP.get(fmt, '%d %b %Y')
        return '{}.strftime("{}")'.format(var, py_fmt)
    source = re.sub(r'([\w.]+)\|date:"([^"]+)"', _date_inline, source)
    source = re.sub(r"([\w.]+)\|date:'([^']+)'", _date_inline, source)

    # 5. {{ var|default:"value" }} → {{ var|default("value") }}
    source = re.sub(r'\|default:"([^"]*)"', r'|default("\1")', source)
    source = re.sub(r"\|default:'([^']*)'", r"|default('\1')", source)
    # {{ var|default:0 }} → {{ var|default(0) }}  (integer/bare value)
    source = re.sub(r'\|default:(\d+)', r'|default(\1)', source)
    source = re.sub(r'\|default:([\w.]+)', r'|default("\1")', source)

    # 6. {{ var|get_full_name }} method calls — handle as attributes
    source = re.sub(r'\{\{\s*request\.user\.get_full_name\s*\}\}',
                    '{{ request_user.full_name }}', source)
    source = re.sub(r'\{\{\s*request\.user\.get_role_display\s*\}\}',
                    '{{ request_user.role_display }}', source)
    source = re.sub(r'\{\{\s*request\.user\.([\w]+)\s*\}\}',
                    r'{{ request_user.\1 }}', source)

    # 7. {% if request.user.role in '...' %} → keep — passes through Jinja2 fine
    #    but need request.user to be accessible as request_user
    source = re.sub(r'request\.user\.role', 'request_user.role', source)
    source = re.sub(r'request\.user\.is_superuser', 'request_user.is_superuser', source)
    source = re.sub(r'request\.user\.first_name', 'request_user.first_name', source)
    source = re.sub(r'request\.user\.last_name', 'request_user.last_name', source)

    # 8. |first|upper → slice(0,1)|upper (Jinja2 compatible)
    source = re.sub(r'\|first\|upper', r'[0:1]|upper', source)
    source = re.sub(r'\|first\|lower', r'[0:1]|lower', source)

    # 9. Django verbatim blocks (if any)
    source = re.sub(r'\{%-?\s*verbatim\s*-?%\}', '', source)
    source = re.sub(r'\{%-?\s*endverbatim\s*-?%\}', '', source)

    # 10. |escapejs → |e (Jinja2 HTML escape; close enough for JS strings)
    source = re.sub(r'\|escapejs', r'|replace("\'","\\\'") ', source)

    # 11. {% cycle 'a' 'b' %} → remove (cosmetic only, alternating row classes)
    source = re.sub(r"\{%-?\s*cycle\s+(?:'[^']*'|\"[^\"]*\"|\w+)(?:\s+(?:'[^']*'|\"[^\"]*\"|\w+))*\s*-?%\}", '', source)

    # 12. {{ var|floatformat:N }} → {{ "%.Nf" % var }}  (approximate)
    source = re.sub(r'\|floatformat:(\d+)', lambda m: f'|round({m.group(1)})', source)

    # 13. |truncatechars:N → [:N]
    source = re.sub(r'\|truncatechars:(\d+)', r'[:\1]', source)

    # 14. |add:N (numeric) → +N  — can't do in filter, strip
    source = re.sub(r'\|add:(\d+)', r'', source)

    # 15. |intcomma — Jinja2 doesn't have it; strip
    source = re.sub(r'\|intcomma', '', source)

    # 16. |pluralize → '' (strip — cosmetic)
    source = re.sub(r'\|pluralize(?::"[^"]*")?', '', source)

    # 17. forloop.counter / forloop.first etc → loop.index / loop.first
    source = source.replace('forloop.counter0', 'loop.index0')
    source = source.replace('forloop.counter',  'loop.index')
    source = source.replace('forloop.first',    'loop.first')
    source = source.replace('forloop.last',     'loop.last')

    # 18. {% url 'name' arg %} → /name/
    source = re.sub(r"\{%-?\s*url\s+'([^']+)'[^%]*%\}", r'/\1/', source)
    source = re.sub(r'\{%-?\s*url\s+"([^"]+)"[^%]*%\}', r'/\1/', source)

    return source


class DjangoCompatLoader(BaseLoader):
    """Jinja2 loader that preprocesses Django-style templates on the fly."""

    def __init__(self, search_paths: list[str]):
        self._loader = FileSystemLoader(search_paths, encoding='utf-8')

    def get_source(self, environment: Environment, template: str):
        raw, path, uptodate = self._loader.get_source(environment, template)
        return _preprocess(raw), path, uptodate

    def list_templates(self):
        return self._loader.list_templates()


# ── Mock user object for template context ─────────────────────────────────────

class _TemplateUser:
    """Provides template context for request.user fields."""
    role         = 'super_admin'
    username     = 'admin'
    first_name   = 'ALIS-X'
    last_name    = 'Admin'
    is_superuser = True
    is_active    = True
    full_name    = 'ALIS-X Admin'
    role_display = 'System Administrator'
    photo        = None

    def in_roles(self, *roles):
        return True   # super_admin sees everything


_DEFAULT_USER = _TemplateUser()


def _build_context(extra: dict | None = None) -> dict:
    """Build Jinja2 template context with sensible defaults."""
    ctx = {
        'today':        date_today.today(),
        'now':          datetime.now(),
        'request_user': _DEFAULT_USER,
        'system_version': settings.app_version,
        'debug':        settings.debug,
    }
    if extra:
        ctx.update(extra)
    return ctx


# ── Startup / Shutdown ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('ALIS-X starting up — offline-first mode…')
    create_all_tables()
    await _seed_default_data()
    logger.info('Database ready.')

    # AI services: probe asynchronously — never block startup
    import asyncio
    asyncio.create_task(_probe_ai_services())

    yield
    logger.info('ALIS-X shutting down.')


async def _probe_ai_services():
    """
    Background AI service probe on startup.
    Does not block — system is operational regardless of AI status.
    """
    import asyncio
    await asyncio.sleep(2)   # let app fully start first
    try:
        from ai_services.local_llm import is_available as ollama_ok, pull_model_if_missing
        from ai_services.cloud_llm import is_available as cloud_ok

        local_up = await ollama_ok()
        cloud_up = await cloud_ok()

        logger.info('AI Status — Local(Ollama): %s | Cloud(Claude): %s',
                    '✓ Online' if local_up else '✗ Offline',
                    '✓ Online' if cloud_up  else '✗ Offline (using local/rules)')

        if local_up:
            # Pull model in background if not already present
            asyncio.create_task(pull_model_if_missing())
        else:
            logger.info('System running in OFFLINE mode — rules engine + coded responses active')

    except Exception as e:
        logger.warning('AI probe error (non-critical): %s', e)


async def _seed_default_data():
    """Create default hospital, departments, admin user, and test rules if empty."""
    from core.database import SessionLocal
    from models.core_config import Hospital, LaboratoryDepartment, TestCatalog
    from models.core_config import TestInterpretationRule, ReflexTestRule
    from models.user import User

    db = SessionLocal()
    try:
        # Default hospital
        hospital = db.query(Hospital).first()
        if not hospital:
            hospital = Hospital(
                name='JORINOVA NEXUS Default Hospital',
                address='Rwanda', district='Kigali', phone='+250000000000',
                hospital_type='public', has_lab=True,
            )
            db.add(hospital)
            db.flush()
            logger.info('Default hospital created.')

        # Admin user
        if not db.query(User).filter(User.username == 'admin').first():
            admin = User(
                username='admin', email='admin@alis-x.rw',
                first_name='ALIS-X', last_name='Admin',
                hashed_password=hash_password('Admin@2026'),
                role='super_admin', is_superuser=True, is_active=True,
                hospital_id=hospital.id,
            )
            db.add(admin)
            logger.info('Admin user created: admin / Admin@2026')

        db.commit()

        # Seed inventory if empty
        from models.inventory import InventoryItem
        if db.query(InventoryItem).count() == 0:
            _seed_inventory(db, hospital)

        # Seed specimen types if empty
        from services.worklist_service import seed_specimen_types
        from models.worklist import SpecimenTypeConfig
        if db.query(SpecimenTypeConfig).count() == 0:
            seeded = seed_specimen_types(db)
            logger.info('Specimen types seeded: %d', seeded)

        # Load test rules if empty
        if db.query(TestCatalog).count() == 0:
            logger.info('Loading test catalog and rules…')
            from services.test_rules_loader import load_test_rules
            await load_test_rules(db, hospital)
            logger.info('Test rules loaded.')

    except Exception as e:
        logger.error(f'Seed error: {e}')
        db.rollback()
    finally:
        db.close()


def _seed_inventory(db, hospital):
    """Seed essential lab inventory items into PostgreSQL."""
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
    logger.info('Inventory seeded: %d items', len(items))


async def _load_test_rules(db, hospital):
    """Load comprehensive test catalog — same data as Django management command."""
    from models.core_config import (LaboratoryDepartment, TestCatalog,
                                    TestInterpretationRule, ReflexTestRule)
    # Import the data from the services module
    try:
        from services.test_rules_data import DEPARTMENTS, TESTS, RULES, REFLEX
        dept_map: dict[str, LaboratoryDepartment] = {}
        for d in DEPARTMENTS:
            dept = LaboratoryDepartment(
                code=d['code'], name=d['name'], abbreviation=d['abbr'],
                color_hex=d['color'], order=d['order'], hospital_id=hospital.id,
            )
            db.add(dept)
            db.flush()
            dept_map[d['code']] = dept

        test_map: dict[str, TestCatalog] = {}
        for t in TESTS:
            code, name, short, dept_code, unit, specimen, tube, tat, price, ref, order = t
            dept = dept_map.get(dept_code)
            if not dept:
                continue
            test = TestCatalog(
                code=code, name=name, short_name=short, department_id=dept.id,
                unit=unit, specimen_type=specimen, tube_type=tube,
                tat_hours=tat, price=price, reference_range=ref,
                order_in_dept=order, is_active=True,
            )
            db.add(test)
            db.flush()
            test_map[code] = test

        for r in RULES:
            code, flag, interp, sig, causes, actions, req_doc, doc_msg, doc_urg = r
            test = test_map.get(code)
            if not test:
                continue
            db.add(TestInterpretationRule(
                test_id=test.id, flag_trigger=flag, interpretation=interp,
                clinical_significance=sig, possible_causes=causes,
                recommended_actions=actions, requires_doctor_confirmation=req_doc,
                doctor_message=doc_msg, doctor_urgency=doc_urg or '',
            ))

        for r in REFLEX:
            trig_code, trig_flag, sug_code, rtype, reason, dept_name, note = r
            trigger   = test_map.get(trig_code)
            suggested = test_map.get(sug_code)
            if not trigger or not suggested:
                continue
            db.add(ReflexTestRule(
                trigger_test_id=trigger.id, trigger_flag=trig_flag,
                suggested_test_id=suggested.id, suggestion_type=rtype,
                reason=reason, suggested_department=dept_name, note_to_doctor=note,
            ))

        db.commit()
    except ImportError:
        logger.warning('test_rules_data.py not found — test catalog not loaded.')


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title     = settings.app_name,
    version   = settings.app_version,
    description = 'Hospital Laboratory Information System — FastAPI + Hybrid AI',
    docs_url  = '/api/docs',
    redoc_url = '/api/redoc',
    lifespan  = lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

# CORS — restrict origins in production (never use '*' in production)
_ALLOWED_ORIGINS = (
    [o.strip() for o in settings.allowed_hosts.split(',') if o.strip()]
    if not settings.debug
    else ['*']
)
if settings.debug:
    logger.warning('CORS: allow_origins=["*"] (debug mode — restrict in production!)')
else:
    logger.info('CORS origins: %s', _ALLOWED_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS if not settings.debug else ['*'],
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allow_headers=['Authorization', 'Content-Type', 'X-Request-ID'],
    expose_headers=['X-Request-ID'],
    max_age=600,
)

# ── Rate Limiting (slowapi) ───────────────────────────────────────────────────
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(key_func=get_remote_address, default_limits=['200/minute'])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info('Rate limiter: active (200/min global, 5/min on login)')
except ImportError:
    logger.warning('slowapi not installed — rate limiting disabled. Run: pip install slowapi')
    limiter = None

# ── Security headers middleware ───────────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
import uuid

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        request_id = str(uuid.uuid4())[:8]
        response = await call_next(request)
        response.headers['X-Request-ID']       = request_id
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options']    = 'DENY'
        response.headers['X-XSS-Protection']   = '1; mode=block'
        if not settings.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ── Static files ──────────────────────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / 'frontend'

# Mount /static/shared/ → frontend/shared/   (matches {% static 'shared/css/...' %})
if (FRONTEND_DIR / 'shared').exists():
    app.mount('/static/shared', StaticFiles(directory=str(FRONTEND_DIR / 'shared')), name='static-shared')

# Mount /static/modules/ → frontend/modules/ (matches {% static 'modules/auth/css/...' %})
if (FRONTEND_DIR / 'modules').exists():
    app.mount('/static/modules', StaticFiles(directory=str(FRONTEND_DIR / 'modules')), name='static-modules')

# Convenience root /static/ also maps to shared for backward compat
if (FRONTEND_DIR / 'shared').exists():
    app.mount('/static', StaticFiles(directory=str(FRONTEND_DIR / 'shared')), name='static')

# Media files (staff photos, uploads)
MEDIA_DIR = Path(__file__).parent.parent / 'media'
MEDIA_DIR.mkdir(exist_ok=True)
app.mount('/media', StaticFiles(directory=str(MEDIA_DIR)), name='media')

# ── Jinja2 template engine (Django-compatible) ────────────────────────────────

_JINJA_ENV: Environment | None = None


def _get_jinja_env() -> Environment:
    global _JINJA_ENV
    if _JINJA_ENV is None:
        search_paths = [
            str(FRONTEND_DIR),                       # root: resolves shared/html/base.html
            str(FRONTEND_DIR / 'shared' / 'html'),   # for {% extends 'base.html' %}
            str(FRONTEND_DIR / 'modules'),            # module templates by folder name
        ]
        loader = DjangoCompatLoader(search_paths)
        _JINJA_ENV = Environment(
            loader=loader,
            autoescape=False,          # HTML already trusted
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=_SilentUndefined,
        )
        # Global helpers
        def static(path: str) -> str:
            """Resolve {% static 'path' %} → /static/path"""
            return f'/static/{path}'

        _JINJA_ENV.globals.update({
            'static':    static,
            'url':       lambda name, *a, **kw: f'/{name}/',
        })

        # Custom filters — bridge Django → Jinja2
        import json as _json
        def _escapejs(value):
            return str(value).replace('\\','\\\\').replace("'","\\'").replace('"','\\"').replace('\n','\\n').replace('\r','\\r')

        _JINJA_ENV.filters.update({
            'escapejs':      _escapejs,
            'intcomma':      lambda v: f'{v:,}' if isinstance(v,(int,float)) else str(v),
            'floatformat':   lambda v,n=2: round(float(v or 0), int(n)),
            'default_if_none': lambda v,d='': d if v is None else v,
            'yesno':         lambda v,vals='yes,no': (vals.split(',') + [''])[0 if v else 1],
            'linebreaks':    lambda v: str(v).replace('\n','<br>'),
            'truncatechars': lambda v,n: str(v)[:n] + '…' if len(str(v)) > n else str(v),
        })
        logger.info('Jinja2 template engine ready.')
    return _JINJA_ENV


from jinja2 import Undefined


class _SilentUndefined(Undefined):
    """Return empty string for missing variables instead of raising."""
    def __str__(self):           return ''
    def __iter__(self):          return iter([])
    def __bool__(self):          return False
    def __getattr__(self, name): return _SilentUndefined()
    def __call__(self, *a, **kw): return _SilentUndefined()

# ── API Routers (register all — graceful import) ─────────────────────────────

_ROUTERS = [
    # Core
    ('routers.sync',            'router'),   # first: ping has no auth
    ('routers.setup',           'router'),   # public — first-run init wizard
    ('routers.auth',            'router'),
    ('routers.patients',        'router'),
    ('routers.laboratory',      'router'),
    ('routers.ai_nexus',        'router'),
    # Clinical departments
    ('routers.hematology',      'router'),
    ('routers.coagulation',     'router'),
    ('routers.serology',        'router'),
    ('routers.urinalysis',      'router'),
    ('routers.microbiology',    'router'),
    ('routers.molecular',       'router'),
    ('routers.biochemistry',    'router'),
    ('routers.blood_bank',      'router'),
    # Operations
    ('routers.inventory',       'router'),
    ('routers.quality',         'router'),
    ('routers.staffhub',        'router'),
    ('routers.surveillance',    'router'),
    ('routers.dashboard',       'router'),
    ('routers.reports',         'router'),
    ('routers.records',         'router'),
    ('routers.notifications',   'router'),
    ('routers.audit',           'router'),
    ('routers.interoperability','router'),
    ('routers.admin_dashboard',  'router'),
    ('routers.voice_biometric',  'router'),
    # Communication & safety
    ('routers.voice',            'router'),
    ('routers.escalation',      'router'),
    ('routers.rejection',       'router'),
    ('routers.documents',       'router'),
    # LIS auto-mapping (lab request form → worklist)
    ('routers.lis_mapping',      'router'),
    # Training / AI demo scenarios
    ('routers.training',         'router'),
    # IoT / analyzer-agnostic ingestion (HL7, ASTM, JSON, CSV; any vendor)
    ('routers.iot',              'router'),
    # PDF reports, SMS notifications, token refresh
    ('routers.pdf_sms',          'router'),
    # Worklist preparation + sample reception
    ('routers.worklist',         'router'),
    # Inline billing at reception
    ('routers.billing',          'router'),
    # Production voice AI assistant
    ('routers.voice_assistant',  'router'),
]

for _mod, _attr in _ROUTERS:
    try:
        import importlib
        _m = importlib.import_module(_mod)
        _r = getattr(_m, _attr)
        app.include_router(_r, prefix='/api/v1')
        logger.info('Router registered: %s', _mod)
    except Exception as _e:
        logger.warning('Router skipped %s: %s', _mod, _e)


# ── Page routes (serve HTML) ──────────────────────────────────────────────────

from fastapi.templating import Jinja2Templates

templates = None
for tmpl_path in [
    FRONTEND_DIR / 'shared' / 'html',
    FRONTEND_DIR / 'modules',
]:
    if tmpl_path.exists():
        templates = Jinja2Templates(directory=str(FRONTEND_DIR))
        break


@app.get('/', include_in_schema=False)
def root():
    return JSONResponse({
        'app': 'JORINOVA NEXUS ALIS-X',
        'status': 'ok',
        'docs': '/docs',
        'health': '/api/v1/health',
    })


def _render(template_path: str, extra_ctx: dict | None = None) -> HTMLResponse:
    """
    Render a template through Jinja2 (with Django-compat preprocessing).
    `template_path` is relative to FRONTEND_DIR, e.g. 'modules/auth/html/login.html'
    """
    env = _get_jinja_env()
    ctx = _build_context(extra_ctx)
    try:
        tmpl = env.get_template(template_path)
        html = tmpl.render(**ctx)
        return HTMLResponse(html)
    except Exception as e:
        logger.warning('Template render error (%s): %s', template_path, e)
        # Fallback — raw file with minimal preprocessing
        full_path = FRONTEND_DIR / template_path
        if full_path.exists():
            raw = full_path.read_text(encoding='utf-8')
            raw = _preprocess(raw)
            # Strip {% extends %} for raw fallback
            raw = re.sub(r'\{%-?\s*extends\s+[\'"][^\'"]+[\'"]\s*-?%\}', '', raw)
            raw = re.sub(r'\{%-?\s*block\s+\w+\s*-?%\}', '', raw)
            raw = re.sub(r'\{%-?\s*endblock\s*\w*\s*-?%\}', '', raw)
            # Replace remaining {{ }} with empty
            raw = re.sub(r'\{\{[^}]+\}\}', '', raw)
            raw = re.sub(r'\{%[^%]+%\}', '', raw)
            return HTMLResponse(raw)
        return HTMLResponse(
            f'<h2>ALIS-X — page not found: {template_path}</h2>', status_code=404)


def _serve_module(module: str, page: str, extra_ctx: dict | None = None) -> HTMLResponse:
    """Serve a frontend HTML module page via Jinja2."""
    template_path = f'modules/{module}/html/{page}'
    full = FRONTEND_DIR / 'modules' / module / 'html' / page
    modules_root = FRONTEND_DIR / 'modules'
    if not full.exists():
        # Search all module dirs (only if the legacy modules root still exists)
        if modules_root.is_dir():
            for mdir in modules_root.iterdir():
                candidate = mdir / 'html' / page
                if candidate.exists():
                    return _render(f'modules/{mdir.name}/html/{page}', extra_ctx)
        return HTMLResponse(
            f'<!DOCTYPE html><html><head><meta charset="UTF-8"><title>ALIS-X 404</title>'
            f'<style>body{{font-family:system-ui;background:#020818;color:#94a3b8;display:flex;align-items:center;justify-content:center;min-height:100vh;flex-direction:column}}'
            f'h1{{color:#6366f1}}a{{color:#6366f1}}</style></head><body>'
            f'<h1>JORINOVA NEXUS ALIS-X</h1>'
            f'<p>Module <b>{module}/{page}</b> not found.</p>'
            f'<a href="/auth/login">← Back to Login</a></body></html>',
            status_code=404,
        )
    return _render(template_path, extra_ctx)


# ── All page routes (38 pages) ────────────────────────────────────────────────

# Auth
@app.get('/auth/login',   response_class=HTMLResponse, include_in_schema=False)
def page_login():           return _serve_module('auth',             'login.html')
@app.get('/auth/profile', response_class=HTMLResponse, include_in_schema=False)
def page_profile():         return _serve_module('auth',             'profile.html')

# Dashboard
@app.get('/dashboard/',   response_class=HTMLResponse, include_in_schema=False)
@app.get('/dashboard',    response_class=HTMLResponse, include_in_schema=False)
def page_dashboard():       return _serve_module('dashboard',        'index.html')

# Patients
@app.get('/patients/',    response_class=HTMLResponse, include_in_schema=False)
@app.get('/patients/hub/',response_class=HTMLResponse, include_in_schema=False)
def page_patients():        return _serve_module('patients',         'patient_hub.html')

# Reception + Worklist Preparation
@app.get('/reception/',                  response_class=HTMLResponse, include_in_schema=False)
@app.get('/reception',                   response_class=HTMLResponse, include_in_schema=False)
def page_reception():                    return _serve_module('reception', 'reception.html')
@app.get('/reception/phlebotomy/',       response_class=HTMLResponse, include_in_schema=False)
def page_phlebotomy():                   return _serve_module('reception', 'phlebotomy.html')
@app.get('/reception/rejection-book/',   response_class=HTMLResponse, include_in_schema=False)
def page_rejection_book():               return _serve_module('reception', 'rejection_book.html')
@app.get('/worklist/',                   response_class=HTMLResponse, include_in_schema=False)
@app.get('/worklist',                    response_class=HTMLResponse, include_in_schema=False)
def page_worklist_home():                return _serve_module('reception', 'worklist.html')
@app.get('/worklist/{department}/',      response_class=HTMLResponse, include_in_schema=False)
@app.get('/worklist/{department}',       response_class=HTMLResponse, include_in_schema=False)
def page_dept_worklist(department: str): return _serve_module('reception', 'worklist_dept.html',
                                             extra_ctx={'department': department})

@app.get('/reception/worklist-prep/{lab_request_id}', response_class=HTMLResponse, include_in_schema=False)
@app.get('/reception/worklist-prep/{lab_request_id}/', response_class=HTMLResponse, include_in_schema=False)
def page_worklist_prep(lab_request_id: int):
    return _serve_module('reception', 'worklist_prep.html',
                         extra_ctx={'lab_request_id': lab_request_id})

# Laboratory
@app.get('/laboratory/',         response_class=HTMLResponse, include_in_schema=False)
def page_lab():                   return _serve_module('laboratory', 'lab_index.html')
@app.get('/laboratory/labels/',  response_class=HTMLResponse, include_in_schema=False)
def page_labels():                return _serve_module('laboratory', 'labels.html')

# Clinical departments
@app.get('/hematology/',         response_class=HTMLResponse, include_in_schema=False)
def page_hematology():            return _serve_module('hematology', 'hematology.html')
@app.get('/biochemistry/',       response_class=HTMLResponse, include_in_schema=False)
def page_biochemistry():          return _serve_module('biochemistry','biochemistry.html')
@app.get('/coagulation/',        response_class=HTMLResponse, include_in_schema=False)
def page_coagulation():           return _serve_module('coagulation','coagulation.html')
@app.get('/laboratory/serology/',response_class=HTMLResponse, include_in_schema=False)
def page_serology():              return _serve_module('serology',   'serology.html')
@app.get('/immunology/',         response_class=HTMLResponse, include_in_schema=False)
def page_immunology():            return _serve_module('immunology', 'immunology.html')
@app.get('/microbiology/',       response_class=HTMLResponse, include_in_schema=False)
@app.get('/laboratory/microbiology/', response_class=HTMLResponse, include_in_schema=False)
def page_microbiology():          return _serve_module('microbiology','microbiology.html')
@app.get('/molecular/',          response_class=HTMLResponse, include_in_schema=False)
@app.get('/laboratory/molecular/', response_class=HTMLResponse, include_in_schema=False)
def page_molecular():             return _serve_module('molecular',  'molecular.html')
@app.get('/urinalysis/',         response_class=HTMLResponse, include_in_schema=False)
def page_urinalysis():            return _serve_module('urinalysis', 'urinalysis.html')
@app.get('/blood-bank/',         response_class=HTMLResponse, include_in_schema=False)
def page_bloodbank():             return _serve_module('blood_bank', 'bloodbank.html')
@app.get('/toxicology/',         response_class=HTMLResponse, include_in_schema=False)
def page_toxicology():            return _serve_module('toxicology', 'toxicology.html')
@app.get('/pathology/',          response_class=HTMLResponse, include_in_schema=False)
def page_pathology():             return _serve_module('pathology',  'pathology.html')

# AI & Intelligence
@app.get('/ai-nexus/',           response_class=HTMLResponse, include_in_schema=False)
def page_ai_nexus():              return _serve_module('ai_nexus',   'ai_nexus.html')
@app.get('/micro-ai/',           response_class=HTMLResponse, include_in_schema=False)
def page_micro_ai():              return _serve_module('micro_ai',   'micro_ai.html')
@app.get('/genomics/',           response_class=HTMLResponse, include_in_schema=False)
def page_genomics():              return _serve_module('genomics',   'genomics.html')
@app.get('/surveillance/',       response_class=HTMLResponse, include_in_schema=False)
def page_surveillance():          return _serve_module('surveillance','surveillance.html')
@app.get('/forecast/',           response_class=HTMLResponse, include_in_schema=False)
def page_forecast():              return _serve_module('forecast',   'forecast.html')
@app.get('/biotrack/',           response_class=HTMLResponse, include_in_schema=False)
def page_biotrack():              return _serve_module('biotrack',   'biotrack.html')

# Quality & Equipment
@app.get('/quality/',              response_class=HTMLResponse, include_in_schema=False)
def page_quality():                return _serve_module('quality', 'quality.html')
@app.get('/quality/levey-jennings',response_class=HTMLResponse, include_in_schema=False)
@app.get('/quality/levey-jennings/',response_class=HTMLResponse, include_in_schema=False)
def page_levey_jennings():         return _serve_module('quality', 'levey_jennings.html')
@app.get('/iot-analyzers/',        response_class=HTMLResponse, include_in_schema=False)
def page_iot():                    return _serve_module('iot_analyzers','iot_analyzers.html')

# Clinical portal
@app.get('/doctor-portal/',      response_class=HTMLResponse, include_in_schema=False)
def page_doctor_portal():         return _serve_module('doctor_portal','doctor_portal.html')
@app.get('/specimen-tracking/',  response_class=HTMLResponse, include_in_schema=False)
def page_specimen():              return _serve_module('specimen_tracking','specimen_tracking.html')

# Finance & Operations
@app.get('/billing/',            response_class=HTMLResponse, include_in_schema=False)
def page_billing():               return _serve_module('billing',    'billing.html')
@app.get('/finaops/',            response_class=HTMLResponse, include_in_schema=False)
def page_finaops():               return _serve_module('finaops',    'finaops.html')
@app.get('/inventory/',          response_class=HTMLResponse, include_in_schema=False)
def page_inventory():             return _serve_module('inventory',  'inventory.html')
@app.get('/nexuscare/',          response_class=HTMLResponse, include_in_schema=False)
def page_nexuscare():             return _serve_module('nexuscare',  'nexuscare.html')
@app.get('/telediagnostic/',     response_class=HTMLResponse, include_in_schema=False)
def page_telediag():              return _serve_module('telediagnostic','telediagnostic.html')

# System & Management
@app.get('/reports/',            response_class=HTMLResponse, include_in_schema=False)
def page_reports():               return _serve_module('reports',    'reports.html')
@app.get('/staffhub/',           response_class=HTMLResponse, include_in_schema=False)
def page_staffhub():              return _serve_module('staffhub',   'staffhub.html')
@app.get('/records/',            response_class=HTMLResponse, include_in_schema=False)
@app.get('/records',             response_class=HTMLResponse, include_in_schema=False)
def page_records():
    from routers.records import BOOKS, BOOK_CATEGORIES
    # Pass books catalogue to template
    books_by_cat = {}
    for cat in BOOK_CATEGORIES:
        books_by_cat[cat] = [(k, {**v, 'id': k}) for k, v in BOOKS.items() if v.get('category') == cat]
    return _serve_module('records', 'records_index.html', {
        'books_by_category': books_by_cat,
        'book_categories': BOOK_CATEGORIES,
        'total_books': len(BOOKS),
    })


@app.get('/records/{book_id}/',  response_class=HTMLResponse, include_in_schema=False)
@app.get('/records/{book_id}',   response_class=HTMLResponse, include_in_schema=False)
def page_book(book_id: str):
    from routers.records import BOOKS
    book = BOOKS.get(book_id)
    if not book:
        return HTMLResponse(f'<h2>Book not found: {book_id}</h2><a href="/records/">← All Books</a>', status_code=404)
    return _serve_module('records', 'records_book.html', {
        'book':    {**book, 'id': book_id},
        'book_id': book_id,
    })
@app.get('/notifications/',      response_class=HTMLResponse, include_in_schema=False)
def page_notifications():         return _serve_module('notifications','notifications.html')
@app.get('/security/',           response_class=HTMLResponse, include_in_schema=False)
def page_security():              return _serve_module('security',   'security.html')
@app.get('/audit-trail/',        response_class=HTMLResponse, include_in_schema=False)
def page_audit():                 return _serve_module('audit',      'audit.html')
@app.get('/interoperability/',   response_class=HTMLResponse, include_in_schema=False)
def page_interop():               return _serve_module('interoperability','interoperability.html')
@app.get('/core-config/',        response_class=HTMLResponse, include_in_schema=False)
def page_core_config():           return _serve_module('core_config','core_config.html')

@app.get('/admin/',              response_class=HTMLResponse, include_in_schema=False)
@app.get('/admin',               response_class=HTMLResponse, include_in_schema=False)
def page_admin():                 return _serve_module('core_config','admin_dashboard.html')

@app.get('/security/voice-training/', response_class=HTMLResponse, include_in_schema=False)
@app.get('/security/voice-training',  response_class=HTMLResponse, include_in_schema=False)
def page_voice_training():        return _serve_module('security','voice_training.html')


@app.get('/api/v1/health')
def health():
    return {'status': 'ok', 'app': settings.app_name, 'version': settings.app_version}


# ── Error handlers ────────────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found(_req: Request, _exc):
    return JSONResponse({'detail': 'Not found'}, status_code=404)


@app.exception_handler(500)
async def server_error(_req: Request, exc: Exception):
    logger.error(f'500 error: {exc}')
    return JSONResponse({'detail': 'Internal server error'}, status_code=500)


# ---------------------------
# Zero-touch demo WebSocket
# ---------------------------

@app.websocket('/ws/zero-touch')
async def ws_zero_touch(websocket: WebSocket):
    await websocket.accept()

    # Simple demo handshake + step loop driven by backend.
    # Frontend is responsible for executing cursor moves / voice / highlights.
    try:
        await websocket.send_json({
            'type': 'STEP',
            'payload': {
                'step': {
                    'id': 'step1_search',
                    'target': 'patient_search',
                    'voiceText': 'Accessing patient records for ID One-Zero-One.',
                    'action': 'type',
                }
            }
        })

        while True:
            msg = await websocket.receive_text()
            # Expect DONE ack from the frontend
            try:
                data = __import__('json').loads(msg)
            except Exception:
                continue

            if data.get('type') != 'DONE':
                continue

            done_step_id = (data.get('payload') or {}).get('stepId')

            if done_step_id == 'step1_search':
                await websocket.send_json({
                    'type': 'STEP',
                    'payload': {
                        'step': {
                            'id': 'step2_analysis',
                            'target': 'lab_results',
                            'voiceText':
                                'Analyzing laboratory data. Hemoglobin is normal, but White Blood Cell count is elevated at 15,000 cells per microliter. Flagging mild leukocytosis.',
                            'action': 'highlight_row',
                        }
                    }
                })
                continue

            if done_step_id == 'step2_analysis':
                await websocket.send_json({
                    'type': 'STEP',
                    'payload': {
                        'step': {
                            'id': 'step3_approve',
                            'target': 'approve_sign',
                            'voiceText':
                                'No critical panic values detected. Results have been automatically validated, digitally signed under Jorinova Nexus protocols, and transmitted.',
                            'action': 'approve',
                        }
                    }
                })
                continue

            if done_step_id == 'step3_approve':
                # Demo complete; send a single terminal message and close.
                await websocket.send_json({
                    'type': 'DONE',
                    'payload': {'stepId': 'complete'}
                })
                await websocket.close()
                return

    except WebSocketDisconnect:
        return
    except Exception:
        # Ensure socket closes on unexpected errors
        try:
            await websocket.close()
        except Exception:
            pass
        return


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='0.0.0.0', port=8000, reload=True, log_level='info')

