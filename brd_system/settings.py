"""
Django settings for brd_system project.

Environment-driven configuration:
  - SQLite for local development (default)
  - PostgreSQL for Azure production (set DB_* env vars)
  - Azure OpenAI for production LLM calls (set AZURE_OPENAI_* env vars)
  - Azure AI Search for static Knowledge Base (set AZURE_SEARCH_* env vars, optional)
"""

import os
import ssl
import warnings
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

# ==============================================================================
# GLOBAL SSL VERIFICATION DISABLE (Bypass Enterprise Proxy & IP Mismatch)
# ==============================================================================
try:
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
    def _custom_unverified_context(*args, **kwargs):
        ctx = ssl._create_unverified_context(*args, **kwargs)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    ssl.create_default_context = _custom_unverified_context
except Exception:
    pass

os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
os.environ['POSTHOG_DISABLED'] = '1'
os.environ['LANGFUSE_DISABLED'] = '1'
warnings.filterwarnings('ignore')
# ==============================================================================

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── App Environment ──────────────────────────────────────────────────────────
# Set APP_ENV=prod in .env for production; anything else is treated as dev.
APP_ENV = os.getenv('APP_ENV', 'dev').lower()

# ─── Security ─────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-key-change-in-production')

# In prod, DEBUG defaults to False unless explicitly overridden to True. In dev, defaults to True.
_default_debug = 'False' if APP_ENV == 'prod' else 'True'
DEBUG = os.getenv('DEBUG', _default_debug) == 'True'

_prod_url = os.getenv('PROD_URL', '').strip()

if APP_ENV == 'prod':
    _allowed = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '').split(',') if h.strip() and h.strip() != '*']
    if _prod_url:
        _prod_host = urlparse(_prod_url).hostname
        if _prod_host and _prod_host not in _allowed:
            _allowed.append(_prod_host)
    ALLOWED_HOSTS = _allowed
else:
    ALLOWED_HOSTS = ['*']

# Required for HTTPS termination in production behind a proxy/load balancer
if APP_ENV == 'prod':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ─── Installed Apps ───────────────────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'django_celery_results',
    'apps.projects',
    'apps.authentication',          # CyberArk OAuth2/OIDC authentication
]

# ─── Middleware ───────────────────────────────────────────────────────────────

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # Serve static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # ── CyberArk auth middleware ───────────────────────────────────────────────
    'apps.authentication.middleware.JWTAuthMiddleware',       # attaches request.auth_payload
    'apps.authentication.middleware.SecurityHeadersMiddleware', # security response headers
]

ROOT_URLCONF = 'brd_system.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'brd_system.wsgi.application'

# ─── Database ─────────────────────────────────────────────────────────────────
# Local dev: SQLite (default)
# Production: PostgreSQL if DB_HOST is set, otherwise safely falls back to SQLite

_default_db_engine = 'postgresql' if (APP_ENV == 'prod' and os.getenv('DB_HOST')) else 'sqlite'
_db_engine = os.getenv('DB_ENGINE', _default_db_engine)

if _db_engine == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'brd_db'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'OPTIONS': {
                'sslmode': os.getenv('DB_SSL_MODE', 'prefer'),
            },
            'CONN_MAX_AGE': 60,  # Keep connections alive for 60s (connection pooling)
        }
    }
else:
    # SQLite — local development default
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ─── Password Validation ──────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Internationalisation ─────────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ─── URL Prefix & Static / Media Files ────────────────────────────────────────
# Flexible URL prefix (e.g. 'chatgpt/'). Set URL_PREFIX= in .env to move back to root (/).
URL_PREFIX = os.getenv('URL_PREFIX', 'chatgpt/').lstrip('/').rstrip('/')
if URL_PREFIX:
    URL_PREFIX = f"{URL_PREFIX}/"

STATIC_URL = f'/{URL_PREFIX}assets/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'assets')
]

LOCALE_PATHS = (os.path.join(os.path.dirname(__file__), '..', 'locale').replace('\\', '/'),)

MEDIA_URL = f'/{URL_PREFIX}media/'
MEDIA_ROOT = BASE_DIR / 'media'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── CORS & CSRF ──────────────────────────────────────────────────────────────

CORS_ALLOW_ALL_ORIGINS = DEBUG  # Open CORS only in debug mode
_cors_origins = [o.strip() for o in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if o.strip()]
if _prod_url and _prod_url not in _cors_origins:
    _cors_origins.append(_prod_url)

CORS_ALLOWED_ORIGINS = _cors_origins if not DEBUG else []
CSRF_TRUSTED_ORIGINS = _cors_origins

# ─── Django REST Framework ────────────────────────────────────────────────────

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [],   # No auth for Phase 1 (Cyberk auth later)
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
}

# ─── Celery ───────────────────────────────────────────────────────────────────

CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 600       # 10 minutes — agents can take longer with context
CELERY_TASK_SOFT_TIME_LIMIT = 540  # Soft limit fires 1 min before hard kill

# ─── Logging ──────────────────────────────────────────────────────────────────

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'apps': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'agents': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'utils': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'celery': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

# ─── Azure OpenAI ─────────────────────────────────────────────────────────────
# Set AI_PROVIDER=azure_openai in .env to use Azure instead of OpenAI/Claude

AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT', '')
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY', '')
AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', '2024-06-01')
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4o')
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT', 'text-embedding-3-large')

# ─── Azure AI Search (Static Knowledge Base) ──────────────────────────────────
# Optional — stub returns empty string if not configured

AZURE_SEARCH_SERVICE_ENDPOINT = os.getenv('AZURE_SEARCH_SERVICE_ENDPOINT', '')
AZURE_SEARCH_INDEX_NAME = os.getenv('AZURE_SEARCH_INDEX_NAME', 'static-corporate-templates-index')
AZURE_SEARCH_API_KEY = os.getenv('AZURE_SEARCH_API_KEY', '')

# ─── File Upload Limits ───────────────────────────────────────────────────────

DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024   # 20 MB max upload
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

# ─── CyberArk OAuth2 / OIDC ──────────────────────────────────────────────────
# Set these in your .env file.  AUTH_URL / TOKEN_URL / USER_INFO_URL are the
# CyberArk Identity (or PAM OIDC) tenant endpoints.

_app_env = APP_ENV

AUTH_CLIENT_ID      = os.getenv('CLIENT_ID', '')
AUTH_CLIENT_SECRET  = os.getenv('CLIENT_SECRET', '')
AUTH_URL            = os.getenv('AUTH_URL', '')        # e.g. https://<tenant>/oauth2/authorize
AUTH_TOKEN_URL      = os.getenv('TOKEN_URL', '')       # e.g. https://<tenant>/oauth2/token
AUTH_USER_INFO_URL  = os.getenv('USER_INFO_URL', '')   # e.g. https://<tenant>/oauth2/userinfo

_dev_url  = 'http://localhost:8000'
AUTH_REDIRECT_URI = _prod_url if _app_env == 'prod' else _dev_url

AUTH_REQUEST_TIMEOUT = 30  # seconds

# HTTP proxy — only applied in production (matches Flask reference)
AUTH_PROXIES = (
    {
        'http':  os.getenv('HTTP_PROXY', ''),
        'https': os.getenv('HTTPS_PROXY', ''),
    }
    if _app_env == 'prod'
    else None
)

# ─── JWT Settings ─────────────────────────────────────────────────────────────
# AUTH_JWT_SECRET       — primary HS256 signing secret
# AUTH_JWT_SECRETS      — comma-separated list of rotation secrets (older/newer)
# Tokens are valid for 8 hours and carry iss + aud claims.

AUTH_JWT_SECRET    = os.getenv('JWT_SECRET', '')
AUTH_JWT_SECRETS   = [s.strip() for s in os.getenv('JWT_SECRETS', '').split(',') if s.strip()]
AUTH_JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
AUTH_JWT_ISSUER    = os.getenv('JWT_ISSUER', 'brd-verification-backend')
AUTH_JWT_AUDIENCE  = os.getenv('JWT_AUDIENCE', 'brd-verification-app')

# ─── Auth Cookie Settings ─────────────────────────────────────────────────────
# HttpOnly JWT cookies — same behaviour as the Flask reference app.

AUTH_COOKIE_HTTPONLY = True
AUTH_COOKIE_MAX_AGE  = 8 * 60 * 60  # 8 hours

if _app_env == 'prod':
    AUTH_COOKIE_SECURE   = True
    AUTH_COOKIE_SAMESITE = 'None'
else:
    AUTH_COOKIE_SECURE   = False
    AUTH_COOKIE_SAMESITE = 'None'  # cross-origin dev (Vite on :5173 → Django on :8000)
