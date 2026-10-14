"""Isolated SQLite + real ASGI/Chromium; simulated hardware, no provider calls."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence' / 'launch-20261011'
POSTGRES = '--postgres' in sys.argv
if POSTGRES:
    EVIDENCE = EVIDENCE / 'postgres-browser'


@contextmanager
def database_env(tmp):
    if not POSTGRES:
        yield {'SQLITE_PATH':str(Path(tmp)/'browser.sqlite3')}
        return
    import psycopg
    from psycopg import sql
    host = os.environ['OGPASS_TEST_POSTGRES_HOST']
    if not host.startswith('/tmp/ogpass-'):
        raise ValueError('Use a disposable PostgreSQL Unix socket under /tmp/ogpass-*')
    port = os.environ.get('OGPASS_TEST_POSTGRES_PORT', '5432')
    user = os.environ.get('OGPASS_TEST_POSTGRES_USER', os.environ.get('USER'))
    db = 'ogpass_browser_' + uuid.uuid4().hex[:12]
    with psycopg.connect(host=host, port=port, user=user, dbname='postgres', autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(db)))
        try:
            yield {'POSTGRES_HOST':host, 'POSTGRES_PORT':port, 'POSTGRES_DB':db,
                   'POSTGRES_USER':user, 'POSTGRES_PASSWORD':'unused', 'POSTGRES_SSLMODE':'disable'}
        finally:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(db)))


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ogpass-browser-') as tmp, database_env(tmp) as db_env:
        env = dict(os.environ, DEBUG='1', OGPASS_ENV='test', OGPASS_MODE='product',
                   SQLITE_PATH=str(Path(tmp) / 'browser.sqlite3'),
                   PUBLIC_URL='http://127.0.0.1', ALLOWED_HOSTS='127.0.0.1,localhost',
                   MP_ACCESS_TOKEN='', MP_WEBHOOK_SECRET='', MP_COLLECTOR_ID='')
        env.pop('POSTGRES_HOST', None)
        env.update(db_env)
        subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'], cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
        seed = '''
import hashlib
from django.contrib.auth import get_user_model
from core.models import Wallet,Reader,Tag
user=get_user_model().objects.create_user('launch-browser',password='local-fixture-98217')
wallet=Wallet.objects.create(user=user)
Tag.objects.create(wallet=wallet,uid='04A1B2C3D4E5F6',card_number='123456789')
Reader.objects.create(name='RC522 TEST SIMULADO',token_hash=hashlib.sha256(b'launch-browser-reader').hexdigest(),amount=1000,cost=700)
'''
        subprocess.run([sys.executable, 'manage.py', 'shell', '-c', seed], cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        env['PUBLIC_URL'] = base
        log = (EVIDENCE / 'browser-server.txt').open('w')
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'config.asgi:application', '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT, env=env, stdout=log, stderr=log)
        try:
            for _ in range(100):
                try:
                    if requests.get(base+'/health/', timeout=.3).status_code == 200: break
                except requests.RequestException: pass
                if server.poll() is not None: raise RuntimeError('ASGI exited')
                time.sleep(.1)
            else: raise RuntimeError('ASGI timeout')
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
                page = browser.new_page(viewport={'width': 390, 'height': 844})
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('response', lambda r: errors.append(f'HTTP {r.status}: {r.url}') if r.status >= 500 else None)
                # Only external sources are stubbed; identity, wallet, events and SSE are real.
                page.route('**/api/external/', lambda route: route.fulfill(json={'stellar': [], 'transport': {'status': 'not_connected'}}))
                page.route('**/api/transport/', lambda route: route.fulfill(json={'cards': [], 'message': 'PRUEBA: fuente externa deshabilitada'}))
                page.goto(base+'/login/')
                page.locator('[name=username]').fill('launch-browser')
                page.locator('[name=password]').fill('local-fixture-98217')
                page.get_by_role('button', name='Ingresar', exact=True).click()
                page.locator('.public-id').wait_for()
                page.wait_for_function("document.querySelector('#live-status').textContent.includes('en vivo')")
                for asset in ('/static/app.css', '/static/css/launch.css', '/static/components/launch.js'):
                    assert requests.get(base+asset, timeout=3).status_code == 200, asset
                event_id = str(uuid.uuid4())
                payload = {'event_id':event_id,'reader':'rc522','technology':'NFC','protocol':'ISO14443A','uid':'04A1B2C3D4E5F6','metadata':{'sak':8,'atqa':4}}
                started = time.monotonic()
                response = requests.post(base+'/api/v1/credentials/scan/', json=payload, headers={'Authorization':'Bearer launch-browser-reader'}, timeout=5)
                assert response.status_code == 201, response.text
                page.get_by_text('Credencial detectada', exact=True).wait_for(timeout=7000)
                latency = round((time.monotonic()-started)*1000)
                assert '04A1B2C3D4E5F6' not in page.locator('body').inner_text()
                assert page.locator('#balance').inner_text().strip() == '$0'
                sizes = []
                for width in (375, 390, 430, 768, 1440):
                    page.set_viewport_size({'width':width, 'height':900})
                    page.evaluate("""() => { if (!document.getElementById('test-watermark')) { const n=document.createElement('div');n.id='test-watermark';n.textContent='PRUEBA LOCAL · lector simulado · sin fondos reales';n.style.cssText='background:#fff0bf;padding:10px;text-align:center;font-size:12px';document.body.prepend(n); } }""")
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Overflow at {width}'
                    page.screenshot(path=str(EVIDENCE/f'mobile-{width}.png'), full_page=True)
                    sizes.append(width)
                assert not errors, errors
                browser.close()
                result = {'status':'PASS', 'widths':sizes, 'hardware_event_visible_ms':latency, 'js_errors':errors,
                          'hardware':'simulated HTTP', 'funds':'none', 'database':'temporary PostgreSQL' if POSTGRES else 'temporary SQLite', 'production_verified':False}
                (EVIDENCE/'browser.json').write_text(json.dumps(result, indent=2)+'\n')
                print(json.dumps(result))
        finally:
            server.terminate()
            try: server.wait(timeout=10)
            except subprocess.TimeoutExpired: server.kill(); server.wait()
            log.close()


if __name__ == '__main__':
    main()
