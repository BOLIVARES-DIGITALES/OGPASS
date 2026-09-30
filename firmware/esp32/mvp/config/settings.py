import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv('DEBUG', '0') == '1'
SECRET_KEY = os.getenv('SECRET_KEY', 'local-only-' + 'x'*50) if DEBUG else os.environ['SECRET_KEY']
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
PUBLIC_URL = os.getenv('PUBLIC_URL', 'http://localhost:8000').rstrip('/')
INSTALLED_APPS = ['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','core']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware','core.middleware.RateLimitMiddleware']
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
if os.getenv('POSTGRES_HOST'):
    postgres_host = os.environ['POSTGRES_HOST']
    postgres_sslmode = os.getenv('POSTGRES_SSLMODE', 'prefer' if DEBUG else ('disable' if postgres_host == 'db' else 'require'))
    DATABASES = {'default': {
        'ENGINE':'django.db.backends.postgresql',
        'HOST':postgres_host,
        'PORT':os.getenv('POSTGRES_PORT','5432'),
        'NAME':os.getenv('POSTGRES_DB','ogpass'),
        'USER':os.getenv('POSTGRES_USER','ogpass'),
        'PASSWORD':os.environ['POSTGRES_PASSWORD'],
        'CONN_MAX_AGE':int(os.getenv('POSTGRES_CONN_MAX_AGE','0')),
        'DISABLE_SERVER_SIDE_CURSORS':os.getenv('POSTGRES_DISABLE_SERVER_SIDE_CURSORS','1') == '1',
        'OPTIONS':{'sslmode':postgres_sslmode},
    }}
else:
    if not DEBUG: raise ImproperlyConfigured('Production requires PostgreSQL')
    DATABASES = {'default':{'ENGINE':'django.db.backends.sqlite3','NAME':Path(os.getenv('SQLITE_PATH', BASE_DIR/'db.sqlite3')),'OPTIONS':{'timeout':20}}}
AUTH_PASSWORD_VALIDATORS = [{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}]
LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR/'staticfiles'
STATICFILES_DIRS = [BASE_DIR/'static']
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
CSRF_TRUSTED_ORIGINS = [PUBLIC_URL]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO','https')
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SESSION_COOKIE_AGE = 43200
MP_ACCESS_TOKEN = os.getenv('MP_ACCESS_TOKEN','')
MP_WEBHOOK_SECRET = os.getenv('MP_WEBHOOK_SECRET','')
MP_COLLECTOR_ID = os.getenv('MP_COLLECTOR_ID','')
PAYMENTS_ENABLED = all([MP_ACCESS_TOKEN, MP_WEBHOOK_SECRET, MP_COLLECTOR_ID]) and PUBLIC_URL.startswith('https://')
CREDENTIAL_ENCRYPTION_KEY = os.getenv('CREDENTIAL_ENCRYPTION_KEY', SECRET_KEY if DEBUG else '')
CREDENTIAL_HMAC_KEY = os.getenv('CREDENTIAL_HMAC_KEY', SECRET_KEY if DEBUG else '')
MOVIRED_BALANCE_API_URL = os.getenv('MOVIRED_BALANCE_API_URL','')
MOVIRED_BALANCE_API_TOKEN = os.getenv('MOVIRED_BALANCE_API_TOKEN','')
MOVIRED_ALLOWED_HOSTS = tuple(filter(None, os.getenv('MOVIRED_ALLOWED_HOSTS','api.movired.cl,widget.movired.cl').split(',')))
STELLAR_TESTNET_URL = 'https://horizon-testnet.stellar.org'
STELLAR_MAINNET_URL = 'https://horizon.stellar.org'
# Mainnet is read-only; no automatic migration or mixing with CLP.
DATA_UPLOAD_MAX_MEMORY_SIZE = 32768
LOGGING = {'version':1,'disable_existing_loggers':False,'handlers':{'console':{'class':'logging.StreamHandler'}},'root':{'handlers':['console'],'level':'INFO'}}
