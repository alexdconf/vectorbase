"""
Django settings for vectorbase project.
"""

from pathlib import Path

import environ

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
env = environ.Env(
    DEBUG=(bool, False),
    GLOBAL_DAILY_QUOTA=(int, 10000),
    SEARCH_RATE_LIMIT=(str, "100/d"),
    SECRET_KEY=(str, "change-me-in-production"),
    ALLOWED_HOSTS=(str, "localhost,127.0.0.1"),
    VECTORS_DB_NAME=(str, "postgres"),
    VECTORS_DB_USER=(str, "postgres"),
    VECTORS_DB_PASSWORD=(str, "test"),
    VECTORS_DB_HOST=(str, "localhost"),
    VECTORS_DB_PORT=(int, 5432),
    SCHEMA_CONFIG_PATH=(str, "schema.yaml"),
)

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env(
    "SECRET_KEY",
    default="django-insecure-iv8f4h+%s1jtga^+@$kb#)-hnyeax=mwz61^((7w)9c64v!@8g",
)
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # "django.contrib.admin",
    # "django.contrib.auth",
    "django.contrib.contenttypes",
    # "django.contrib.sessions",
    # "django.contrib.messages",
    "django.contrib.staticfiles",
    "portal"
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serve static files in production
    # "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    # "django.contrib.auth.middleware.AuthenticationMiddleware",
    # "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "vectorbase.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                # "django.contrib.auth.context_processors.auth",
                # "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "vectorbase.wsgi.application"

# ---------------------------------------------------------------------------
# Databases
# ---------------------------------------------------------------------------
DATABASES = {
    "default": env.db(
        "DEFAULT_DB_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    ),
    "vectors": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("VECTORS_DB_NAME", default="postgres"),
        "USER": env("VECTORS_DB_USER", default="postgres"),
        "PASSWORD": env("VECTORS_DB_PASSWORD", default="test"),
        "HOST": env("VECTORS_DB_HOST", default="localhost"),
        "PORT": env("VECTORS_DB_PORT", default="5432"),
    },
}

DATABASE_ROUTERS = ["portal.routers.VectorsDatabaseRouter"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Cache  (django-ratelimit uses the default cache)
# Use CACHE_URL env var in production, e.g. redis://localhost:6379/1
# ---------------------------------------------------------------------------
CACHES = {
    "default": env.cache("CACHE_URL", default="locmemcache://"),
}

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
# AUTH_PASSWORD_VALIDATORS = [
#     {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
#     {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
#     {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
#     {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
# ]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"

# Absolute path where collectstatic writes files for production serving.
STATIC_ROOT = BASE_DIR / "staticfiles"

# Use WhiteNoise's compressed + hashed storage in production.
# WhiteNoise serves files directly from Django without a separate web server.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ---------------------------------------------------------------------------
# VectorBase settings
# ---------------------------------------------------------------------------
# Path to the YAML schema config (relative paths are resolved from BASE_DIR)
_schema_config_path = env("SCHEMA_CONFIG_PATH", default="schema.yaml")
SCHEMA_CONFIG_PATH = (
    Path(_schema_config_path)
    if Path(_schema_config_path).is_absolute()
    else BASE_DIR / _schema_config_path
)

# Per-IP rate limit (django-ratelimit format: N/s|m|h|d)
SEARCH_RATE_LIMIT: str = env("SEARCH_RATE_LIMIT")

# Maximum total searches allowed per calendar day (UTC) across all users
GLOBAL_DAILY_QUOTA: int = env("GLOBAL_DAILY_QUOTA")

# ---------------------------------------------------------------------------
# Logging settings
# ---------------------------------------------------------------------------
ENABLE_LOGGING = True
LOG_BACKEND = "logs.backends.stdout.StdoutBackend"
LOG_BACKEND_OPTIONS = {"logs.backends.stdout.StdoutBackend"}   # passed as kwargs to the backend
