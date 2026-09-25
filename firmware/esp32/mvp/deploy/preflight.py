"""Run in production environment before migrations and startup."""
import os,sys
from urllib.parse import urlparse
errors=[]
for key in ('SECRET_KEY','POSTGRES_PASSWORD','POSTGRES_ADMIN_PASSWORD','DOMAIN','PUBLIC_URL','ALLOWED_HOSTS'):
    v=os.getenv(key,'')
    if not v or 'REPLACE' in v:errors.append(f'{key}: required')
if len(os.getenv('SECRET_KEY',''))<50:errors.append('SECRET_KEY: use at least 50 random characters')
if len(os.getenv('POSTGRES_PASSWORD',''))<24:errors.append('POSTGRES_PASSWORD: use at least 24 random characters')
if os.getenv('POSTGRES_USER') not in ('ogpass','ogpass_owner') or os.getenv('POSTGRES_DB')!='ogpass':errors.append('Initial DB scripts require POSTGRES_USER=ogpass and POSTGRES_DB=ogpass')
if os.getenv('DEBUG')!='0':errors.append('DEBUG must be 0')
if os.getenv('POSTGRES_HOST')!='db':errors.append('POSTGRES_HOST must be db for this compose')
if urlparse(os.getenv('PUBLIC_URL','')).scheme!='https':errors.append('PUBLIC_URL must use HTTPS')
if urlparse(os.getenv('PUBLIC_URL','')).hostname!=os.getenv('DOMAIN'):errors.append('PUBLIC_URL and DOMAIN mismatch')
if os.getenv('DOMAIN') not in os.getenv('ALLOWED_HOSTS','').split(','):errors.append('DOMAIN must be in ALLOWED_HOSTS')
if errors:print('\n'.join(errors));sys.exit(1)
payments=all(os.getenv(k) for k in ('MP_ACCESS_TOKEN','MP_WEBHOOK_SECRET','MP_COLLECTOR_ID'))
print('Deployment config: OK. Payments: '+('configured, live acceptance still required' if payments else 'DISABLED: credentials missing'))
