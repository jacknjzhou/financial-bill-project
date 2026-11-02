"""对账系统 Django 配置。

标准 src layout：本文件位于 src/financial_bill/settings.py，
manage.py / conftest.py 负责把 src/ 加入 sys.path。
所有可变配置一律 env 驱动（compose 注入 / 本地 .env）。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # src/

# 本地开发可放 backend/.env（gitignore）；容器内由 compose 注入，.env 不存在则忽略
load_dotenv(BASE_DIR.parent / ".env")


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


SECRET_KEY = env("SECRET_KEY", "dev-insecure-secret-key")
DEBUG = env("DEBUG", "0") == "1"
ALLOWED_HOSTS = ["*"]  # 内网系统
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("FRONTEND_ORIGIN").split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    # 业务 app（apps/ 统一目录，后续任务逐个启用）：
    "apps.core",
    "apps.accounts",
    # "apps.meta", "apps.rules", "apps.dataio", "apps.engine", "apps.disputes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # 强制改密闸门（必须排在 AuthenticationMiddleware 之后）
    "apps.core.middleware.MustChangePasswordGate",
]

ROOT_URLCONF = "financial_bill.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "financial_bill.wsgi.application"
ASGI_APPLICATION = "financial_bill.asgi.application"

AUTH_USER_MODEL = "accounts.User"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", "recon"),
        "USER": env("DB_USER", "recon"),
        "PASSWORD": env("DB_PASSWORD", "recon"),
        "HOST": env("DB_HOST", "localhost"),
        "PORT": env("DB_PORT", "5432"),
    }
}

# Redis / Celery
REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ALWAYS_EAGER = env("CELERY_TASK_ALWAYS_EAGER", "0") == "1"
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TIMEZONE = "Asia/Shanghai"
CELERY_TASK_TIME_LIMIT = 1800  # 30min 硬杀
CELERY_TASK_SOFT_TIME_LIMIT = 1500

# DRF / OpenAPI
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "apps.core.errors.recon_exception_handler",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "对账系统",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# 时间：存 UTC，展示 Asia/Shanghai
TIME_ZONE = "Asia/Shanghai"
USE_TZ = True
LANGUAGE_CODE = "zh-hans"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR.parent / "staticfiles"

# 邮件（站内 + 邮件告警；默认 console 后端便于开发）
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = int(env("EMAIL_PORT", "25") or 25)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env("EMAIL_USE_TLS", "0") == "1"
EMAIL_FROM = env("EMAIL_FROM", "recon@local")
ALERT_EMAIL_TO = [a.strip() for a in env("ALERT_EMAIL_TO").split(",") if a.strip()]

# SSO / OIDC（T2B 启用；本地账号密码登录始终可用）
OIDC_ENABLED = env("OIDC_ENABLED", "0") == "1"
OIDC_ISSUER = env("OIDC_ISSUER")
OIDC_CLIENT_ID = env("OIDC_CLIENT_ID")
OIDC_CLIENT_SECRET = env("OIDC_CLIENT_SECRET")
OIDC_ROLE_MAP = env("OIDC_ROLE_MAP", "{}")  # JSON：IdP claim → 角色
