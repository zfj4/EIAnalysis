"""
Test settings — inherits from settings.py and overrides DATABASES to use
SQLite so the test suite can run without a live PostgreSQL server.
"""
from .settings import *  # noqa: F401, F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_db.sqlite3',  # noqa: F405
    }
}
