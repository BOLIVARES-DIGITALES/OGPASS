"""Isolated PostgreSQL + actual Uvicorn + Chromium acceptance test.
Only fixture money/readers. Creates and removes its own temporary database.
"""
import hashlib,json,os,subprocess,sys,time,uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import psycopg
from psycopg import sql
import requests
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
DB='ogpass_realtime_'+uuid.uuid4().hex[:8]
HOST='http://127.0.0.1:8011'
base={'host':'/tmp/ogpass-postgres','user':'uniquedev','dbname':'postgres'}
with psycopg.connect(**base,autocommit=True) as conn:
    conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(DB)))
env={**os.environ,'DEBUG':'1','POSTGRES_HOST':'/tmp/ogpass-postgres','POSTGRES_USER':'uniquedev','POSTGRES_DB':DB,'POSTGRES_PASSWORD':'unused','DJANGO_SETTINGS_MODULE':'config.settings'}
server=None
log=(ROOT/'evidence/realtime-server.txt').open('w')
try:
    subprocess.run([sys.executable,str(ROOT/'manage.py'),'migrate','--noinput'],env=env,check=True,stdout=subprocess.DEVNULL)
    os.environ.update(env);sys.path.insert(0,str(ROOT))
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.db import connections
    from django.test import override_settings
    from core.models import Wallet,Reader,TopUp,Tag,Preload,Operation
    from core.services import apply_payment,balance,reconciliation
    issuer_user=get_user_model().objects.create_user('test-administrator',password='fixture-admin-only-9821',is_staff=True)
    recipient_user=get_user_model().objects.create_user('test-recipient',password='fixture-user-only-8921')
    issuer=Wallet.objects.create(user=issuer_user);recipient=Wallet.objects.create(user=recipient_user)
    Reader.objects.create(name='TEST-READER',token_hash=hashlib.sha256(b'test-reader-only').hexdigest())
    t=TopUp.objects.create(wallet=issuer,amount=10000,key=uuid.uuid4())
    with override_settings(MP_COLLECTOR_ID='fixture'):
        apply_payment({'id':'fixture-realtime','external_reference':str(t.pk),'live_mode':True,'collector_id':'fixture','currency_id':'CLP','transaction_amount':10000,'status':'approved','fee_details':[]})
    connections.close_all()
    server=subprocess.Popen([sys.executable,'-m','uvicorn','config.asgi:application','--app-dir',str(ROOT),'--host','127.0.0.1','--port','8011','--log-level','warning'],env=env,stdout=log,stderr=log)
    for _ in range(100):
        try:
            if requests.get(HOST+'/health/',timeout=.3).status_code==200:break
        except requests.RequestException:pass
        if server.poll() is not None:raise RuntimeError('Test ASGI server exited')
        time.sleep(.1)
    else:raise RuntimeError('Test ASGI server did not start')
    def dbcall(fn):
        def work():
            try:return fn()
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=1) as pool:return pool.submit(work).result()
    reader_headers={'Authorization':'Bearer test-reader-only'}
    def scan(uid):
        response=requests.post(HOST+'/api/reader/scans/',json={'uid':uid,'key':str(uuid.uuid4())},headers=reader_headers,timeout=5)
        response.raise_for_status();return response.json()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        user_page=browser.new_page(viewport={'width':390,'height':844})
        admin_page=browser.new_page(viewport={'width':1440,'height':1000})
        errors=[]
        for page in [user_page,admin_page]:
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('response',lambda r:errors.append(str(r.status)+' '+r.url) if r.status>=500 else None)
        def login(page,username,password):
            page.goto(HOST+'/login/');page.locator('[name=username]').fill(username);page.locator('[name=password]').fill(password);page.get_by_role('button',name='Ingresar',exact=True).click()
        login(user_page,'test-recipient','fixture-user-only-8921')
        user_page.wait_for_function("document.querySelector('#live-status').textContent.includes('en vivo')")
        login(admin_page,'test-administrator','fixture-admin-only-9821')
        admin_page.goto(HOST+'/ops/')
        admin_page.locator('#preload-recipient').fill('test-recipient');admin_page.locator('#preload-amount').fill('3000')
        begin=time.monotonic();admin_page.get_by_role('button',name='Reservar y asignar',exact=True).click()
        user_page.get_by_role('button',name='Activar $3.000',exact=True).wait_for(timeout=3000)
        reservation_ms=round((time.monotonic()-begin)*1000)
        assert dbcall(lambda:balance(recipient))==0
        assert dbcall(lambda:balance(issuer))==7000
        begin=time.monotonic();user_page.get_by_role('button',name='Activar $3.000',exact=True).click()
        user_page.wait_for_function("document.querySelector('#balance').textContent.includes('3.000')",timeout=3000)
        activation_ms=round((time.monotonic()-begin)*1000)
        admin_page.wait_for_function("document.querySelector('#ops-preload-rows').textContent.includes('Activada')",timeout=3000)
        pairing=scan('04AB1234567890');assert pairing['status']=='pairing_required'
        user_page.locator('#card-number').fill('114309782');user_page.get_by_role('button',name='Guardar tarjeta y consultar',exact=True).click()
        admin_page.locator('[data-reader-select]').wait_for();admin_page.locator('[data-reader-select]').select_option(index=1)
        admin_page.once('dialog',lambda dialog:dialog.accept());admin_page.get_by_role('button',name='Vincular tarjeta detectada').click()
        admin_page.wait_for_function("document.querySelector('#ops-reader-message').textContent.includes('asociada')")
        user_page.wait_for_function("document.querySelector('#live-status').textContent.includes('en vivo')")
        begin=time.monotonic();result=scan('04AB1234567890')
        assert result['available_balance']==3000 and result['status']=='balance'
        user_page.wait_for_function("document.querySelector('#scan-status').textContent.includes('114309782') && document.querySelector('#scan-status').textContent.includes('3.000')",timeout=3000)
        scan_ms=round((time.monotonic()-begin)*1000)
        assert dbcall(lambda:Operation.objects.count())==0
        admin_page.locator('#preload-recipient').fill('test-recipient');admin_page.locator('#preload-amount').fill('2000');admin_page.get_by_role('button',name='Reservar y asignar',exact=True).click()
        user_page.get_by_role('button',name='Activar $2.000',exact=True).wait_for(timeout=3000)
        new_scan=scan('041234567890AB')
        old_id=dbcall(lambda:Tag.objects.get(uid='04AB1234567890').pk)
        # Replacement compatibility endpoint; the simplified UI requests association only.
        result=user_page.evaluate('''async data => {const r=await fetch('/tags/',{method:'POST',headers:{'X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value},body:new URLSearchParams(data)});return r.status;}''',{'card_number':'998877665','pairing_code':new_scan['pairing_code'],'consent':'yes','replace_tag':str(old_id)})
        assert result==200
        user_page.get_by_role('button',name='Activar $2.000',exact=True).wait_for(timeout=3000)
        assert scan('04AB1234567890')['status']=='disabled'
        assert scan('041234567890AB')['available_balance']==3000
        user_page.get_by_role('button',name='Activar $2.000',exact=True).click()
        user_page.wait_for_function("document.querySelector('#balance').textContent.includes('5.000')",timeout=3000)
        assert scan('041234567890AB')['available_balance']==5000
        # Network interruption + reconnection must recover the latest state.
        user_page.context.set_offline(True)
        dbcall(lambda:Tag.objects.filter(uid='041234567890AB').update(active=False))
        from core.realtime import emit_event
        dbcall(lambda:emit_event(recipient.pk,'test_reconnect'))
        user_page.context.set_offline(False)
        user_page.reload()
        user_page.wait_for_function("document.querySelector('#scan-status').textContent.includes('desactivada')",timeout=5000)
        dbcall(lambda:Tag.objects.filter(uid='041234567890AB').update(active=True))
        dbcall(lambda:emit_event(recipient.pk,'test_reconnect_complete'))
        user_page.wait_for_function("document.querySelector('#scan-status').textContent.includes('5.000')",timeout=3000)
        def screenshot(page,name):
            page.evaluate("""() => {const n=document.createElement('div');n.style='background:#fff1c7;padding:12px;text-align:center';n.textContent='PRUEBA AUTOMATIZADA · FONDOS Y LECTOR SIMULADOS';document.body.prepend(n)}""")
            page.screenshot(path=str(ROOT/'evidence'/name),full_page=True)
        screenshot(user_page,'realtime-user.png');admin_page.reload();screenshot(admin_page,'preloads-admin.png')
        report=dbcall(reconciliation)
        assert report['trial_balance']==0 and report['preload_liability']==0
        assert not errors,errors
        result={'scope':'isolated fixtures, no real money or physical reader','server':'Uvicorn ASGI + PostgreSQL LISTEN/NOTIFY','reservation_to_browser_ms':reservation_ms,'activation_to_balance_ms':activation_ms,'scan_to_browser_ms':scan_ms,'recipient_balance':dbcall(lambda:balance(recipient)),'issuer_balance':dbcall(lambda:balance(issuer)),'card_replaced_without_balance_loss':True,'pending_preload_survives_replacement':True,'reconnect_resync':True,'admin_status_updated_live':True,'balance_scans_create_operations':dbcall(lambda:Operation.objects.count()),'browser_errors':errors,'reconciliation':report}
        (ROOT/'evidence/realtime-flow.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2),flush=True)
        browser.close()
finally:
    if server:
        server.terminate()
        try:server.wait(timeout=8)
        except subprocess.TimeoutExpired:server.kill();server.wait()
    log.close()
    try:
        from django.db import connections
        connections.close_all()
    except Exception:pass
    with psycopg.connect(**base,autocommit=True) as conn:
        conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(DB)))
