"""Opt-in Chromium test: real Django HTTP, two isolated browser identities."""
import json
import os
from pathlib import Path
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from core.models import Tag, Wallet, Journal
from backend.apps.tag_portal.models import TagPortal


@override_settings(ALLOWED_HOSTS=['localhost', '127.0.0.1', 'testserver'])
class TagPortalBrowserTests(StaticLiveServerTestCase):
    def test_mobile_activation_visitor_isolation_and_block(self):
        from playwright.sync_api import sync_playwright
        user = get_user_model().objects.create_user('portal-browser', password='fixture-browser-83472', first_name='Titular de prueba')
        tag = Tag.objects.create(wallet=Wallet.objects.create(user=user), uid='04AACCDDEEFF00')
        portal = TagPortal.objects.create(tag=tag)
        path = f'/w/{portal.code}/'
        evidence = Path(os.getenv('OGPASS_PORTAL_EVIDENCE_DIR', 'evidence/tag-portal-20261012/browser'))
        evidence.mkdir(parents=True, exist_ok=True)
        errors = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            owner_context = browser.new_context(viewport={'width':390, 'height':844})
            visitor_context = browser.new_context(viewport={'width':390, 'height':844})
            page = owner_context.new_page()
            visitor = visitor_context.new_page()
            for tab in (page, visitor):
                tab.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(self.live_server_url+path)
            self.assertEqual(page.locator('main').get_attribute('data-state'), 'new')
            page.get_by_role('link', name='Ingresar como titular').click()
            page.locator('[name=username]').fill('portal-browser')
            page.locator('[name=password]').fill('fixture-browser-83472')
            page.get_by_role('button', name='Ingresar', exact=True).click()
            page.get_by_role('button', name='Activar mi acceso').click()
            page.get_by_role('heading', name='Hola, Titular de prueba').wait_for()
            visitor.goto(self.live_server_url+path)
            self.assertEqual(visitor.locator('main').get_attribute('data-state'), 'visitor')
            self.assertNotIn('Titular de prueba', visitor.content())
            self.assertEqual(page.evaluate('localStorage.length'), 0)
            self.assertEqual(visitor.evaluate('localStorage.length'), 0)
            for width in (375,390,430,768,1440):
                page.set_viewport_size({'width':width, 'height':900})
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                page.screenshot(path=str(evidence/f'owner-{width}.png'), full_page=True)
            visitor.screenshot(path=str(evidence/'visitor-390.png'), full_page=True)
            page.get_by_text('Seguridad del llavero', exact=True).click()
            page.get_by_role('checkbox').check()
            page.get_by_role('button', name='Bloquear llavero', exact=True).click()
            page.wait_for_url('**/my/tags/')
            self.assertIn('Llavero bloqueado', page.locator('main').inner_text())
            response = visitor.reload()
            self.assertEqual(response.status, 404)
            self.assertEqual(visitor.locator('main').get_attribute('data-state'), 'unavailable')
            self.assertFalse(errors, errors)
            browser.close()
        tag.refresh_from_db()
        self.assertFalse(tag.active)
        self.assertEqual(Journal.objects.count(), 0)
        (evidence/'result.json').write_text(json.dumps({'status':'PASS', 'widths':[375,390,430,768,1440],
            'separate_browser_contexts':True, 'js_errors':errors, 'funds':'none',
            'hardware':'not exercised; URLs only', 'screenshots':'test users only'}, indent=2)+'\n')
