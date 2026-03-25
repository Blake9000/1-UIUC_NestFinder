from django.conf import STATICFILES_STORAGE_ALIAS
from .base import *

DEBUG = False
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static'
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

# Replace it with your name:
ALLOWED_HOSTS = ['localhost', '127.0.0.1','bmackin2.pythonanywhere.com', 'nestfinder.blake4it.com']

CSRF_TRUSTED_ORIGINS = ["https://nestfinder.blake4it.com"]

# Database for the development server
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        # put the DB in project-root/data/db.sqlite3
        'NAME': BASE_DIR / 'data' / 'db.sqlite3',
    }
}

CORS_ALLOWED_ORIGINS = [
    "https://vega.github.io",
    'https://bmackin2.pythonanywhere.com',
    'https://nestfinder.blake4it.com',
    'http://nestfinder.blake4it.com',
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True