"""Verification against disposable PostgreSQL in /tmp, never production."""
import os,subprocess,sys,json,uuid
from pathlib import Path
import psycopg
ROOT=Path(__file__).resolve().parents[1]
with psycopg.connect(host='/tmp/ogpass-postgres',user='uniquedev',dbname='postgres',autocommit=True) as c:
    for role in ('ogpass_owner','ogpass'):
        if not c.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone():c.execute(f'CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB')
    if not c.execute("SELECT 1 FROM pg_database WHERE datname='ogpass_runtime_check'").fetchone():c.execute('CREATE DATABASE ogpass_runtime_check OWNER ogpass_owner')
with psycopg.connect(host='/tmp/ogpass-postgres',user='ogpass_owner',dbname='ogpass_runtime_check',autocommit=True) as c:
    c.execute('GRANT USAGE ON SCHEMA public TO ogpass')
    c.execute('ALTER DEFAULT PRIVILEGES FOR ROLE ogpass_owner IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO ogpass')
    c.execute('ALTER DEFAULT PRIVILEGES FOR ROLE ogpass_owner IN SCHEMA public GRANT USAGE,SELECT ON SEQUENCES TO ogpass')
env={**os.environ,'DEBUG':'1','POSTGRES_HOST':'/tmp/ogpass-postgres','POSTGRES_USER':'ogpass_owner','POSTGRES_DB':'ogpass_runtime_check','POSTGRES_PASSWORD':'unused'}
subprocess.run([sys.executable,str(ROOT/'manage.py'),'migrate','--noinput'],env=env,check=True)
os.environ.update({**env,'POSTGRES_USER':'ogpass','DJANGO_SETTINGS_MODULE':'config.settings'})
sys.path.insert(0,str(ROOT))
import django
django.setup()
from django.contrib.auth import get_user_model
from django.test import override_settings
from core.models import Wallet,TopUp
from core.services import apply_payment,balance
u=get_user_model().objects.create_user('runtime-'+uuid.uuid4().hex[:8])
w=Wallet.objects.create(user=u)
t=TopUp.objects.create(wallet=w,amount=1000,key=uuid.uuid4())
with override_settings(MP_COLLECTOR_ID='test'):
    apply_payment({'id':str(uuid.uuid4().int)[:18],'external_reference':str(t.pk),'collector_id':'test','live_mode':True,'currency_id':'CLP','transaction_amount':1000,'status':'approved','fee_details':[]})
assert balance(w)==1000
checks={}
with psycopg.connect(host='/tmp/ogpass-postgres',user='ogpass',dbname='ogpass_runtime_check',autocommit=True) as c:
    for name,sql in [('no_truncate','TRUNCATE core_entry'),('no_drop','ALTER TABLE core_entry DISABLE TRIGGER ALL'),('no_seal_tampering',"INSERT INTO ogpass_journal_seal VALUES ('00000000-0000-0000-0000-000000000001')")]:
        try:c.execute(sql)
        except psycopg.Error:checks[name]=True
        else:raise AssertionError(name+' unexpectedly permitted')
print(json.dumps({'source':'isolated_test_database','runtime_payment_posted':True,**checks},indent=2))
