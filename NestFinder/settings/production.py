# Paste in and as: illinois/settings/production.py
# We will first import everything from base.py (our new settings.py file that we renamed to base.py)
#==================================================================================
from django.conf import STATICFILES_STORAGE_ALIAS

from .base import *

DEBUG = False
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static'
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

# Replace it with your name:
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Database for the development server
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        # put the DB in project-root/data/db.sqlite3
        'NAME': BASE_DIR / 'data' / 'db.sqlite3',
    }
}
