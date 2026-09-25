"""Explicit opt-in browser test. Never enables mock payments in application config."""
import hashlib,hmac,json,os,time,uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import requests
from django.test import LiveServerTestCase,override_settings
from django.db import connection,connections
from django.contrib.auth import get_user_model
from playwright.sync_api import sync_playwright
from core.models import Wallet,Reader,TopUp
from core.services import balance,reconciliation

@override_settings(PAYMENTS_ENABLED=True,MP_COLLECTOR_ID='123',MP_WEBHOOK_SECRET='browser-test-secret',ALLOWED_HOSTS=['localhost','127.0.0.1','testserver'])
class BrowserFlow(LiveServerTestCase):
    @patch('core.adapters.Transport.portal_status',new=lambda self: {'status':'verification_required','checked_at':'2026-09-25T16:00:00+00:00'})
    def test_mobile_checkout_touch_confirm_admin(self):
        if connection.vendor!='postgresql':self.skipTest('Browser test uses PostgreSQL to avoid shared in-memory SQLite connections')
        user=get_user_model().objects.create_user('demo',password='test-only-password-892',is_staff=True)
        wallet=Wallet.objects.create(user=user)
        Reader.objects.create(name='ESP32-001',token_hash=hashlib.sha256(b'browser-reader-token').hexdigest(),amount=1000,cost=700)
        evidence=Path(__file__).resolve().parents[1]/'evidence'
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
            errors=[];http_errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('response',lambda response:http_errors.append(response.url) if response.status>=500 else None)
            page.goto(self.live_server_url+'/login/')
            page.locator('[name=username]').fill('demo');page.locator('[name=password]').fill('test-only-password-892')
            page.get_by_role('button',name='Ingresar',exact=True).click()
            headers={'Authorization':'Bearer browser-reader-token'}
            pair=requests.post(self.live_server_url+'/api/reader/scans/',json={'uid':'04AB1234567890','key':str(uuid.uuid4())},headers=headers,timeout=10).json()
            self.assertEqual(pair['status'],'pairing_required')
            page.locator('#card-number').fill('114309782')
            page.get_by_role('button',name='Guardar tarjeta y consultar',exact=True).click()
            page.locator('#transport-result a').wait_for()
            self.assertIn('CAPTCHA',page.locator('#transport-result').inner_text())
            self.assertIn('114309782',page.locator('#transport-result').inner_text())
            page.screenshot(path=str(evidence/'transport-consultation-test.png'),full_page=True)
            posted=[]
            page.on('request',lambda request:posted.append(request.url) if request.method=='POST' else None)
            page.get_by_role('button',name='Monitor NFC / Copiar a llavero',exact=True).click()
            page.locator('#nfc-monitor[open]').wait_for()
            page.wait_for_function("document.querySelector('#nfc-live').textContent.includes('en línea')")
            self.assertIn('114309782',page.locator('#nfc-source').inner_text())
            self.assertTrue(page.get_by_role('button',name='Escribir en llavero · No disponible').is_disabled())
            page.get_by_role('button',name='Ver demostración de copia',exact=True).click()
            page.wait_for_function("document.querySelector('#nfc-demo-result').textContent.includes('Demostración terminada')")
            self.assertEqual(posted,[])
            self.assertIn('No se escribió ningún dato',page.locator('#nfc-demo-result').inner_text())
            page.screenshot(path=str(evidence/'nfc-monitor-demo-test.png'),full_page=True)
            page.keyboard.press('Escape')
            page.locator('#nfc-monitor').wait_for(state='hidden')
            page.get_by_role('button',name='Monitor NFC / Copiar a llavero',exact=True).click()
            self.assertTrue(page.locator('#nfc-demo').is_hidden())
            page.get_by_role('button',name='Cerrar monitor NFC',exact=True).click()

            page.goto(self.live_server_url+'/ops/')
            page.wait_for_selector('[data-reader-select]')
            page.locator('[data-reader-select]').select_option(index=1)
            page.once('dialog',lambda dialog:dialog.accept())
            page.get_by_role('button',name='Vincular tarjeta detectada').click()
            page.wait_for_function("document.querySelector('#ops-reader-message').textContent.includes('asociada')")
            page.get_by_role('button',name='Copiar y reescribir en la próxima tarjeta NFC').click()
            page.locator('#copy-dialog[open]').wait_for()
            self.assertIn('No se han escrito datos',page.locator('#copy-dialog').inner_text())
            page.get_by_role('button',name='Cerrar',exact=True).click()
            page.screenshot(path=str(evidence/'reader-panel-test.png'),full_page=True)
            page.goto(self.live_server_url+'/')
            page.locator('#my-card > summary').click()
            page.wait_for_selector('.linked-card')
            page.route('https://www.mercadopago.cl/checkout/test',lambda route:route.fulfill(status=200,content_type='text/html',body='<h1>Checkout controlado: PRUEBA, sin fondos reales</h1>'))
            with patch('core.adapters.MercadoPago.checkout',return_value=('fixture-preference','https://www.mercadopago.cl/checkout/test')):
                page.locator('#amount').fill('5000');page.get_by_role('button',name='Pagar con Mercado Pago').click()
                page.wait_for_url('https://www.mercadopago.cl/checkout/test')
            def db_read(fn):
                def work():
                    try:return fn()
                    finally:connections.close_all()
                with ThreadPoolExecutor(max_workers=1) as pool:return pool.submit(work).result()
            topup=db_read(lambda:TopUp.objects.get(wallet=wallet))
            payment={'id':777,'external_reference':str(topup.pk),'live_mode':True,'collector_id':123,'currency_id':'CLP','transaction_amount':5000,'status':'approved','fee_details':[{'amount':100}]}
            ts=str(int(time.time()));manifest=f'id:777;request-id:browser;ts:{ts};'
            sig=hmac.new(b'browser-test-secret',manifest.encode(),hashlib.sha256).hexdigest()
            with patch('core.adapters.MercadoPago.payment',return_value=payment):
                r=requests.post(self.live_server_url+'/api/payments/webhook/?data.id=777',json={'type':'payment','data':{'id':777}},headers={'x-signature':f'ts={ts},v1={sig}','x-request-id':'browser'},timeout=10)
                self.assertEqual(r.status_code,200)
            self.assertEqual(db_read(lambda:balance(wallet)),5000)
            page.goto(self.live_server_url+'/');page.wait_for_function("document.querySelector('#balance').textContent.includes('5.000')")
            def screenshot(name):
                page.evaluate("""() => {let n=document.getElementById('test-label');if(!n){n=document.createElement('div');n.id='test-label';n.style='background:#fff1c7;padding:12px;text-align:center;font-size:12px';n.textContent='PRUEBA AUTOMATIZADA · PROVEEDOR Y LECTOR SIMULADOS';document.body.prepend(n)}}""")
                page.screenshot(path=str(evidence/name),full_page=True)
            screenshot('mobile-funded.png')
            consulted=requests.post(self.live_server_url+'/api/reader/scans/',json={'uid':'04AB1234567890','key':str(uuid.uuid4())},headers=headers,timeout=10).json()
            self.assertEqual(consulted['status'],'balance');self.assertEqual(consulted['available_balance'],5000)
            page.wait_for_function("document.querySelector('#scan-status').textContent.includes('5.000')")
            screenshot('card-balance.png')
            key=str(uuid.uuid4());headers={'Authorization':'Bearer browser-reader-token'}
            r=requests.post(self.live_server_url+'/api/reader/scans/',json={'uid':'04AB1234567890','key':key,'purpose':'payment'},headers=headers,timeout=10)
            self.assertEqual(r.json()['status'],'pending')
            page.get_by_role('button',name='Confirmar pago').wait_for(timeout=10000)
            screenshot('mobile-confirm.png')
            page.get_by_role('button',name='Confirmar pago').click()
            page.wait_for_function("document.querySelector('#balance').textContent.includes('4.000')")
            screenshot('mobile-completed.png')
            r=requests.get(self.live_server_url+'/api/reader/scans/'+key+'/',headers=headers,timeout=10)
            self.assertEqual(r.json()['status'],'approved')
            page.set_viewport_size({'width':1440,'height':1000});page.goto(self.live_server_url+'/ops/')
            page.get_by_role('heading',name='Todo cuenta.').wait_for()
            screenshot('admin-reconciliation.png')
            self.assertEqual(errors,[]);self.assertEqual(http_errors,[])
            report=db_read(reconciliation);self.assertEqual(report['result'],200)
            (evidence/'browser-flow.json').write_text(json.dumps({'kind':'AUTOMATED_TEST_ONLY','payment_source':'mock canonical response; no real money','reader_source':'HTTP client; no physical device','initial_balance':0,'topup':5000,'balance_after_topup':5000,'operation_amount':1000,'operation_cost':700,'operation_margin':300,'payment_fee':100,'balance_after_operation':db_read(lambda:balance(wallet)),'report':report,'card_pairing':'nine-digit request + staff confirms explicit authenticated reader scan','balance_query_debits':0,'browser_js_errors':errors,'http_server_errors':http_errors},indent=2))
            browser.close()
