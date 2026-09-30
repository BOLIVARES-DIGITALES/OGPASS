"""Valida una configuración Supabase sin imprimir secretos."""
import os
import sys
from urllib.parse import urlparse

errors = []
required = (
    'SECRET_KEY', 'DOMAIN', 'PUBLIC_URL', 'ALLOWED_HOSTS',
    'POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB', 'POSTGRES_USER',
    'POSTGRES_PASSWORD', 'CREDENTIAL_ENCRYPTION_KEY', 'CREDENTIAL_HMAC_KEY',
)
for key in required:
    value = os.getenv(key, '')
    if not value or 'REPLACE' in value:
        errors.append(f'{key}: required')

if len(os.getenv('SECRET_KEY', '')) < 50:
    errors.append('SECRET_KEY: use at least 50 random characters')
if len(os.getenv('POSTGRES_PASSWORD', '')) < 16:
    errors.append('POSTGRES_PASSWORD: database password is missing or too short')
if len(os.getenv('CREDENTIAL_ENCRYPTION_KEY', '')) < 32:
    errors.append('CREDENTIAL_ENCRYPTION_KEY: use at least 32 random characters')
if len(os.getenv('CREDENTIAL_HMAC_KEY', '')) < 32:
    errors.append('CREDENTIAL_HMAC_KEY: use at least 32 random characters')
if os.getenv('CREDENTIAL_ENCRYPTION_KEY') == os.getenv('CREDENTIAL_HMAC_KEY'):
    errors.append('Credential encryption and HMAC keys must be different')
if os.getenv('DEBUG') != '0':
    errors.append('DEBUG must be 0')

host = os.getenv('POSTGRES_HOST', '').lower()
if host and not host.endswith('.supabase.com'):
    errors.append('POSTGRES_HOST must be the Supabase Connect host')
port = os.getenv('POSTGRES_PORT', '')
if port not in ('5432', '6543'):
    errors.append('POSTGRES_PORT must be 5432 (session/direct) or 6543 (transaction pooler)')
if os.getenv('POSTGRES_SSLMODE') not in ('require', 'verify-full'):
    errors.append('POSTGRES_SSLMODE must be require or verify-full')
if port == '6543' and os.getenv('POSTGRES_CONN_MAX_AGE', '0') != '0':
    errors.append('Transaction pooler requires POSTGRES_CONN_MAX_AGE=0')
if os.getenv('POSTGRES_DISABLE_SERVER_SIDE_CURSORS', '1') != '1':
    errors.append('Use POSTGRES_DISABLE_SERVER_SIDE_CURSORS=1 with the pooler')

public_url = urlparse(os.getenv('PUBLIC_URL', ''))
if public_url.scheme != 'https':
    errors.append('PUBLIC_URL must use HTTPS')
if public_url.hostname != os.getenv('DOMAIN'):
    errors.append('PUBLIC_URL and DOMAIN mismatch')
if os.getenv('DOMAIN') not in os.getenv('ALLOWED_HOSTS', '').split(','):
    errors.append('DOMAIN must be in ALLOWED_HOSTS')

if errors:
    print('\n'.join(errors))
    sys.exit(1)
print('Supabase deployment config: OK (secrets were not displayed).')
