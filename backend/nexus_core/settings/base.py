"""
JORINOVA NEXUS ALIS-X
Base Django Settings - NexusCore Engine
"""
import os
from pathlib import Path
try:
    from decouple import config, Csv  # type: ignore
except Exception:  # pragma: no cover
    from .decouple_compat import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR.parent / 'frontend'

SECRET_KEY = config('SECRET_KEY', default='alis-x-nexus-dev-key-change-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

def _optional(*pkgs):
    """Include package in INSTALLED_APPS only if importable."""
    result = []
    for pkg in pkgs:
        try:
            __import__(pkg.replace('-', '_').split('.')[0])
            result.append(pkg)
        except ImportError:
            pass
    return result


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    *_optional('rest_framework_simplejwt'),
    'corsheaders',
    'channels',
    *_optional('django_filters', 'drf_spectacular', 'auditlog', 'import_export'),



    # ALIS-X Core Apps
    'apps.authentication',
    'apps.core_config',
    'apps.patients',
    'apps.reception',
    'apps.laboratory',
    'apps.billing',
    'apps.inventory',
    'apps.reports',
    'apps.notifications',
    'apps.dashboard',
    # ALIS-X Extended Modules
    'apps.staffhub',
    'apps.genomics',
    'apps.surveillance',
    'apps.finaops',
    'apps.nexuscare',
    'apps.ai_nexus',
    'apps.telediagnostic',
    'apps.security',
    'apps.records',
    'apps.micro_ai',
    'apps.biotrack',
    'apps.bloodbank',
    # ── Clinical AI ──
    'apps.hematology',
    'apps.quality',
    'apps.toxicology',
    'apps.pathology',
    # ── Infrastructure ──
    'apps.iot_analyzers',
    'apps.interoperability',
    'apps.doctor_portal',
    'apps.specimen_tracking',
    'apps.forecast',
    'apps.audit',

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.authentication.middleware.SessionTimeoutMiddleware',
    'apps.audit.middleware.SilentAuditMiddleware',
]
try:
    import auditlog  # noqa: F401
    MIDDLEWARE.insert(-1, 'auditlog.middleware.AuditlogMiddleware')
except ImportError:
    pass

ROOT_URLCONF = 'nexus_core.urls'

# Template dirs: frontend/modules/*/html
import glob as _glob
_tmpl_dirs = [FRONTEND_DIR]
for _path in _glob.glob(str(FRONTEND_DIR / 'modules' / '*' / 'html')):
    _tmpl_dirs.append(Path(_path))

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': _tmpl_dirs,
        'APP_DIRS': False,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core_config.context_processors.hospital_context',
                'apps.core_config.context_processors.system_context',
            ],
            'loaders': [
                ('django.template.loaders.filesystem.Loader', _tmpl_dirs),
                'django.template.loaders.app_directories.Loader',
            ],
        },
    },
]

WSGI_APPLICATION = 'nexus_core.wsgi.application'
ASGI_APPLICATION = 'nexus_core.asgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE', default='django.db.backends.sqlite3'),
        'NAME': BASE_DIR / config('DB_NAME', default='alis_x.db'),
        'USER': config('DB_USER', default=''),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default=''),
        'PORT': config('DB_PORT', default=''),
        'OPTIONS': {
            'timeout': 20,
        } if config('DB_ENGINE', default='django.db.backends.sqlite3') == 'django.db.backends.sqlite3' else {},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTH_USER_MODEL = 'authentication.NexusUser'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Kigali'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR.parent / 'staticfiles'
STATICFILES_DIRS = [
    FRONTEND_DIR,
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR.parent / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
_drf_auth = ['rest_framework.authentication.SessionAuthentication']
try:
    import rest_framework_simplejwt  # noqa: F401
    _drf_auth.insert(0, 'rest_framework_simplejwt.authentication.JWTAuthentication')
except ImportError:
    pass

_drf_filters = []
try:
    import django_filters  # noqa: F401
    _drf_filters = ['django_filters.rest_framework.DjangoFilterBackend']
except ImportError:
    pass

_drf_schema = 'rest_framework.schemas.openapi.AutoSchema'
try:
    import drf_spectacular  # noqa: F401
    _drf_schema = 'drf_spectacular.openapi.AutoSchema'
except ImportError:
    pass

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': _drf_auth,
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_FILTER_BACKENDS': _drf_filters,
    'DEFAULT_SCHEMA_CLASS': _drf_schema,
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

# JWT
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
}

# Channels (WebSocket)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# CORS
CORS_ALLOWED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
CORS_ALLOW_CREDENTIALS = True

# Session
SESSION_COOKIE_AGE = config('SESSION_TIMEOUT', default=3600, cast=int)
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True

# Login
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/auth/login/'

# Celery
CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_TIMEZONE = 'Africa/Kigali'

# SMS (Twilio)
TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_PHONE_NUMBER = config('TWILIO_PHONE_NUMBER', default='')

# Hospital Config
HOSPITAL_NAME = config('HOSPITAL_NAME', default='General Hospital')
HOSPITAL_ADDRESS = config('HOSPITAL_ADDRESS', default='Kigali, Rwanda')
HOSPITAL_PHONE = config('HOSPITAL_PHONE', default='')
HOSPITAL_EMAIL = config('HOSPITAL_EMAIL', default='')
HOSPITAL_DISTRICT = config('HOSPITAL_DISTRICT', default='')

# System
SYSTEM_VERSION = config('SYSTEM_VERSION', default='1.0.0')
MAX_LOGIN_ATTEMPTS = config('MAX_LOGIN_ATTEMPTS', default=5, cast=int)

# AI Microservice
AI_MICROSERVICE_URL = config('AI_MICROSERVICE_URL', default='http://localhost:8001')

# Jazzmin Admin
JAZZMIN_SETTINGS = {
    'site_title': 'ALIS-X Admin',
    'site_header': 'JORINOVA NEXUS ALIS-X',
    'site_brand': 'NexusCore',
    'site_icon': None,
    'welcome_sign': 'Welcome to NexusCore Administration',
    'topmenu_links': [{'name': 'Dashboard', 'url': '/dashboard/'}],
    'show_sidebar': True,
    'navigation_expanded': True,
    'hide_apps': [],
    'icons': {
        'authentication': 'fas fa-users-cog',
        'patients': 'fas fa-user-injured',
        'laboratory': 'fas fa-flask',
        'billing': 'fas fa-file-invoice-dollar',
        'inventory': 'fas fa-boxes',
    },
    'default_icon_parents': 'fas fa-chevron-circle-right',
    'default_icon_children': 'fas fa-circle',
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}', 'style': '{'},
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR.parent / 'logs' / 'alis_x.log',
            'formatter': 'verbose',
        },
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'root': {'handlers': ['console', 'file'], 'level': 'INFO'},
}
