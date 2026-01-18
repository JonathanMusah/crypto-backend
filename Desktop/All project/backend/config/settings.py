"""
Django settings for crypto platform project.
"""
import os
from pathlib import Path
import environ
import dj_database_url

env = environ.Env(
    DEBUG=(bool, False)
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Read .env file
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

# Cache configuration - Use Redis if available, fall back to local memory
REDIS_URL = env('REDIS_URL', default=None)

if REDIS_URL:
    # Production: Use Redis from env (Render provides REDIS_URL)
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'IGNORE_EXCEPTIONS': True,  # Don't crash if Redis is unavailable
            }
        }
    }
else:
    # Development/Render free tier: Use local memory cache (no Redis)
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }

# Import local settings if in development mode
if DEBUG:
    try:
        from .local_settings import *
    except ImportError:
        pass

# ALLOWED_HOSTS - In production on Render, disable host checking
# Render uses multiple subdomains, so we accept all
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'crypto-backend-dumz.onrender.com',  # Render domain
    '.onrender.com',  # Allow all Render subdomains
]

# Add custom domains from env if provided
if env('ALLOWED_HOSTS', default=None):
    custom_hosts = env.list('ALLOWED_HOSTS')
    ALLOWED_HOSTS.extend(custom_hosts)

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'channels',  # Add this for WebSocket support
    'config.apps.ConfigConfig',  # Enable SQLite WAL mode
]

# Add django_ratelimit for rate limiting
INSTALLED_APPS.append('django_ratelimit')

INSTALLED_APPS.extend([
    'authentication',
    'wallets',
    # Re-enabling apps now that Pillow is installed
    'orders',
    'notifications',
    'kyc',
    'tutorials',
    'analytics',
    'rates',
    'marketing',
    'support',
    'messaging',
])

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # 'authentication.middleware.IPBanMiddleware',  # DISABLED: Re-enable after migrations run
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'authentication.middleware.UpdateLastSeenMiddleware',  # Update last_seen for online status
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'

# Database - Support DATABASE_URL for Render, fallback to SQLite
if env('DATABASE_URL', default=None):
    DATABASES = {
        'default': dj_database_url.config(
            default=env('DATABASE_URL'),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {
                'timeout': 20,
                'check_same_thread': False,
            },
            'CONN_MAX_AGE': 0,
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'authentication.User'

# Authentication Backends
AUTHENTICATION_BACKENDS = [
    'authentication.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'authentication.middleware.JWTAuthenticationFromCookie',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
}

# JWT Settings
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# CORS Settings - Allow testing and development origins
CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=[
        'http://localhost:3000', 
        'http://127.0.0.1:3000',
        'http://localhost:5500',  # Live Server extension
        'http://127.0.0.1:5500',  # Live Server extension
        'http://localhost:8080',  # Common dev ports
        'http://127.0.0.1:8080',
        'http://localhost:19006', # Expo
        'http://127.0.0.1:19006',
        'exp://localhost:19000',  # Expo
        'exp://127.0.0.1:19000',
    ]
)
CORS_ALLOW_CREDENTIALS = True

# For development, also allow all origins from localhost and 127.0.0.1
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

# Additional CORS headers for development
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Email Configuration
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@cryptoplatform.com')

# Frontend URL for password reset links
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:3000')

# Celery Configuration - Use Redis if available, otherwise use dummy backend
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default=REDIS_URL or 'memory://')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default=REDIS_URL or 'cache+memory://')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = not REDIS_URL  # Run tasks synchronously if no Redis

# Session Configuration
if REDIS_URL:
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # Use database if no Redis

# Django Channels Configuration
ASGI_APPLICATION = 'config.asgi.application'

# Channel Layers (for WebSocket support)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',  # In-memory for free tier
    }
}

# Sentry Configuration
try:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    
    sentry_sdk.init(
        dsn=env('SENTRY_DSN', default=None),
        integrations=[
            DjangoIntegration(
                transaction_style='url',
                middleware_spans=True,
                signals_spans=False,
                cache_spans=False,
            ),
        ],
        traces_sample_rate=1.0,
        send_default_pii=True
    )
except ImportError:
    pass

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'authentication': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'wallets': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'orders': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'notifications': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'rates': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Add file logging only in development
if DEBUG:
    LOGGING['handlers']['file'] = {
        'level': 'INFO',
        'class': 'logging.FileHandler',
        'filename': 'logs/django.log',
        'formatter': 'verbose',
    }
    LOGGING['handlers']['json_file'] = {
        'level': 'INFO',
        'class': 'logging.FileHandler',
        'filename': 'logs/django_json.log',
        'formatter': 'json',
    }
    for logger_name in ['django', 'authentication', 'wallets', 'orders', 'notifications', 'rates']:
        LOGGING['loggers'][logger_name]['handlers'] = ['file', 'json_file']
