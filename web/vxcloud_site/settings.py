from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me-in-production")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "backoffice",
    "blog",
    "cabinet",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "vxcloud_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "blog.context_processors.site_navigation",
            ],
        },
    }
]

WSGI_APPLICATION = "vxcloud_site.wsgi.application"
ASGI_APPLICATION = "vxcloud_site.asgi.application"


def _postgres_from_url(url: str) -> dict[str, str]:
    p = urlparse(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": (p.path or "").lstrip("/"),
        "USER": unquote(p.username or ""),
        "PASSWORD": unquote(p.password or ""),
        "HOST": p.hostname or "127.0.0.1",
        "PORT": str(p.port or 5432),
    }


db_url = os.getenv("DATABASE_URL", "").strip()
if db_url.startswith("postgres://") or db_url.startswith("postgresql://"):
    DATABASES = {"default": _postgres_from_url(db_url)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = os.getenv("TIMEZONE", "Europe/Moscow")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

LOGIN_REDIRECT_URL = "/account/"
LOGOUT_REDIRECT_URL = "/accounts/login/"
AUTHENTICATION_BACKENDS = [
    "cabinet.backends.EmailOrUsernameModelBackend",
    "django.contrib.auth.backends.ModelBackend",
]

EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("DJANGO_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("DJANGO_EMAIL_USE_TLS", "1") == "1"
EMAIL_USE_SSL = os.getenv("DJANGO_EMAIL_USE_SSL", "0") == "1"
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "no-reply@vxcloud.ru")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MAGIC_LINK_SHARED_SECRET = os.getenv("MAGIC_LINK_SHARED_SECRET", "")
MAGIC_LINK_TTL_SECONDS = int(os.getenv("MAGIC_LINK_TTL_SECONDS", "600"))
MAGIC_LINK_RATE_LIMIT_PER_MINUTE = int(os.getenv("MAGIC_LINK_RATE_LIMIT_PER_MINUTE", "30"))
WEBHOOK_RATE_LIMIT_PER_MINUTE = int(os.getenv("WEBHOOK_RATE_LIMIT_PER_MINUTE", "240"))
ACCOUNT_MAGIC_URL_TEMPLATE = os.getenv(
    "ACCOUNT_MAGIC_URL_TEMPLATE",
    "https://vxcloud.ru/auth/tg/{token}",
)

TELEGRAM_WEBAPP_BOT_TOKEN = os.getenv("TELEGRAM_WEBAPP_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_WEBAPP_AUTH_MAX_AGE_SECONDS = int(os.getenv("TELEGRAM_WEBAPP_AUTH_MAX_AGE_SECONDS", "600"))
TELEGRAM_LOGIN_AUTH_MAX_AGE_SECONDS = int(
    os.getenv("TELEGRAM_LOGIN_AUTH_MAX_AGE_SECONDS", str(TELEGRAM_WEBAPP_AUTH_MAX_AGE_SECONDS))
)

PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "yookassa")
PAYMENT_REFERENCE_BASE_URL = os.getenv("PAYMENT_REFERENCE_BASE_URL", "https://pay.vxcloud.ru/mock")
PAYMENT_REFERENCE_WEBHOOK_SECRET = os.getenv("PAYMENT_REFERENCE_WEBHOOK_SECRET", "")
PAYMENT_YOOKASSA_SHOP_ID = os.getenv("PAYMENT_YOOKASSA_SHOP_ID", "")
PAYMENT_YOOKASSA_API_KEY = os.getenv("PAYMENT_YOOKASSA_API_KEY", "")
PAYMENT_YOOKASSA_WEBHOOK_SECRET = os.getenv("PAYMENT_YOOKASSA_WEBHOOK_SECRET", "")
ENABLE_CARD_PAYMENTS = os.getenv("ENABLE_CARD_PAYMENTS", "0") == "1"
CARD_PAYMENT_AMOUNT_MINOR = int(os.getenv("CARD_PAYMENT_AMOUNT_MINOR", "24900"))
CARD_PAYMENT_CURRENCY = os.getenv("CARD_PAYMENT_CURRENCY", "RUB")
VPN_PUBLIC_HOST = os.getenv("VPN_PUBLIC_HOST", "").strip()
VPN_PUBLIC_PORT = int(os.getenv("VPN_PUBLIC_PORT", "29940"))
VPN_TAG = os.getenv("VPN_TAG", "VXcloud").strip() or "VXcloud"
WORDPRESS_PUBLIC_SITE_ENABLED = os.getenv("WORDPRESS_PUBLIC_SITE_ENABLED", "0") == "1"
WORDPRESS_CONTENT_READONLY = os.getenv("WORDPRESS_CONTENT_READONLY", "0") == "1"
WORDPRESS_PUBLIC_SITE_URL = os.getenv("WORDPRESS_PUBLIC_SITE_URL", "").strip().rstrip("/")
X_FRAME_OPTIONS = os.getenv("DJANGO_X_FRAME_OPTIONS", "SAMEORIGIN")

