import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from core.models import Audit, Journal, Operation, Reader, Tag, Wallet, WalletEvent
from core.services import touch, decide
from backend.apps.credentials.services import sync_tag
from backend.apps.tag_portal.models import TagPortal
from backend.apps.tag_portal.services import activate, block, payload_info, provision_for_owner


@override_settings(PUBLIC_URL='https://ogpass.example', OGPASS_MODE='product')
class TagPortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('portal-owner', first_name='PRIVATE-NAME', password='fixture-password-83274')
        cls.other = get_user_model().objects.create_user('portal-other')
        cls.staff = get_user_model().objects.create_user('portal-staff', is_staff=True)
        cls.wallet = Wallet.objects.create(user=cls.owner)
        Wallet.objects.create(user=cls.other)
        Wallet.objects.create(user=cls.staff)
        cls.tag = Tag.objects.create(uid='04AABBCCDDEE00', card_number='876543219', wallet=cls.wallet)
        cls.credential = sync_tag(cls.tag)
        cls.portal = TagPortal.objects.create(tag=cls.tag)

    def setUp(self):
        self.path = reverse('tag-portal', args=[self.portal.code])
        self.api = reverse('tag-portal-state', args=[self.portal.code])

    def test_visitor_allowlist_no_private_data_in_json_or_html(self):
        activate(self.portal.code, self.owner)
        for user in (None, self.other, self.staff):
            self.client.logout()
            if user:
                self.client.force_login(user)
            # Knowing the code/forging WOOD-style holder fields confers no access.
            response = self.client.get(self.api, {'_holder': str(uuid.uuid4()), 'user_id': self.owner.pk})
            data = response.json()
            self.assertEqual(data['state'], 'visitor')
            self.assertEqual(set(data), {'state', 'title', 'message', 'theme', 'can_activate', 'can_manage', 'path'})
            body = response.content.decode() + self.client.get(self.path).content.decode()
            for secret in (self.tag.uid, 'PRIVATE-NAME', 'portal-owner', self.tag.card_number, str(self.credential.identity.private_id)):
                self.assertNotIn(secret, body)
            self.assertFalse(data['can_manage'])

    def test_new_inventory_cannot_be_claimed_by_public_code(self):
        portal = TagPortal.objects.create()
        path = reverse('tag-portal', args=[portal.code])
        self.assertEqual(self.client.get(path).context['portal']['state'], 'new')
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(path+'activate/').status_code, 403)
        portal.refresh_from_db()
        self.assertIsNone(portal.tag_id)
        self.assertIsNone(portal.activated_at)

    def test_activation_is_owner_only_idempotent_and_non_financial(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.path+'activate/').status_code, 403)
        self.client.force_login(self.owner)
        self.assertTrue(self.client.get(self.api).json()['can_activate'])
        for _ in range(2):
            self.assertRedirects(self.client.post(self.path+'activate/'), self.path)
        self.assertEqual(Audit.objects.filter(event='tag_portal_activated').count(), 1)
        self.assertEqual(WalletEvent.objects.filter(kind='tag_portal_activated').count(), 1)
        self.assertEqual(self.client.get(self.api).json()['owner']['display_name'], 'PRIVATE-NAME')
        self.assertEqual(Journal.objects.count(), 0)
        self.assertEqual(Operation.objects.count(), 0)

    def test_csrf_and_http_methods_are_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.path+'activate/').status_code, 403)
        client.get(self.path)
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post(self.path+'activate/', HTTP_X_CSRFTOKEN=token).status_code, 302)
        self.assertEqual(client.post(self.path+'block/', {'confirm':'block'}).status_code, 403)
        self.assertEqual(client.get(self.path+'activate/').status_code, 405)

    def test_disabled_tag_and_portal_fail_closed_immediately(self):
        activate(self.portal.code, self.owner)
        self.client.force_login(self.owner)
        for model, field in ((Tag, 'active'), (TagPortal, 'enabled')):
            obj = self.tag if model is Tag else self.portal
            model.objects.filter(pk=obj.pk).update(**{field:False})
            self.assertEqual(self.client.get(self.api).json(), {'state':'unavailable'})
            self.assertEqual(self.client.get(self.path).status_code, 404)
            self.assertEqual(self.client.post(self.path+'activate/').status_code, 403)
            model.objects.filter(pk=obj.pk).update(**{field:True})

    def test_owner_block_prevents_pending_debit_without_mutating_ledger(self):
        reader = Reader.objects.create(name='portal-reader', amount=1000, cost=700)
        op = touch(reader, self.tag.uid, uuid.uuid4())
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.path+'block/', {'confirm':'block'}).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.path+'block/').status_code, 400)
        for _ in range(2):
            self.assertEqual(self.client.post(self.path+'block/', {'confirm':'block'}).status_code, 302)
        op = decide(self.wallet, op.pk, True)
        self.assertEqual(op.status, 'declined')
        self.assertEqual(op.reason, 'account_or_tag_disabled')
        self.credential.refresh_from_db()
        self.assertEqual(self.credential.status, 'disabled')
        self.assertEqual(Audit.objects.filter(event='tag_blocked_by_owner').count(), 1)
        self.assertEqual(Journal.objects.count(), 0)

    def test_provisioning_and_list_are_owner_scoped(self):
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get('/my/tags/'), self.portal.code)
        self.assertEqual(self.client.post(reverse('provision-tag-portal', args=[self.tag.pk])).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(provision_for_owner(self.tag.pk, self.owner).pk, self.portal.pk)
        other_tag = Tag.objects.create(wallet=self.wallet, uid='11223344')
        a = provision_for_owner(other_tag.pk, self.owner)
        b = provision_for_owner(other_tag.pk, self.owner)
        self.assertEqual(a.pk, b.pk)
        self.assertNotEqual(a.code, self.portal.code)
        self.assertContains(self.client.get('/my/tags/'), a.code)
        other_tag.refresh_from_db()
        self.assertEqual(other_tag.wallet_id, self.wallet.pk)

    def test_dynamic_copy_is_escaped_and_not_private_model_serialization(self):
        TagPortal.objects.filter(pk=self.portal.pk).update(title='<script>alert(1)</script>', message='Nueva experiencia', theme='dark')
        response = self.client.get(self.path)
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>')
        self.assertContains(response, 'theme-dark')
        self.assertContains(response, 'Nueva experiencia')

    def test_cache_referrer_csp_and_logout_remove_owner_view(self):
        activate(self.portal.code, self.owner)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.api).json()['state'], 'owner')
        self.client.post('/logout/')
        self.assertEqual(self.client.get(self.api).json()['state'], 'visitor')
        for path in (self.path, self.api, '/w/not-a-real-code/'):
            response = self.client.get(path)
            self.assertEqual(response['Cache-Control'], 'no-store, private')
            self.assertEqual(response['Referrer-Policy'], 'same-origin')
            self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.assertIn("default-src 'none'", self.client.get(self.path)['Content-Security-Policy'])

    def test_rate_limit_cannot_be_reset_by_changing_code(self):
        self.client.force_login(self.owner)
        with patch('core.middleware.time.time', return_value=1234567890):
            for n in range(10):
                self.assertEqual(self.client.post(f'/w/missing-{n}/activate/').status_code, 403)
            response = self.client.post(self.path+'activate/')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Cache-Control'], 'no-store, private')

    def test_login_returns_to_portal_with_httponly_cookie(self):
        response = self.client.post('/login/', {'username':self.owner.username, 'password':'fixture-password-83274', 'next':self.path})
        self.assertRedirects(response, self.path)
        self.assertTrue(response.cookies['sessionid']['httponly'])
        self.assertEqual(response.cookies['sessionid']['samesite'], 'Lax')

    def test_register_preserves_local_next_and_rejects_external_redirect(self):
        for n, target in enumerate((self.path, '//evil.invalid/', 'https://evil.invalid/', '/\\evil.invalid/')):
            self.client.logout()
            response = self.client.post('/register/', {'username':f'new-portal-user-{n}', 'password1':'fixture-register-pass-882', 'password2':'fixture-register-pass-882', 'next':target})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, self.path if n == 0 else '/')

    def test_ndef_capacity_and_origin_validation(self):
        data = payload_info(self.portal)
        self.assertTrue(data['fits_ntag213'])
        self.assertEqual(data['ntag213_bytes'], len(data['uri'].removeprefix('https://').encode())+8)
        with override_settings(PUBLIC_URL='https://'+'a'*140+'.example'):
            self.assertFalse(payload_info(self.portal)['fits_ntag213'])
        for origin in ('https://user:secret@example.org', 'https://example.org/path', 'javascript:alert(1)'):
            with override_settings(PUBLIC_URL=origin), self.assertRaises(ValidationError):
                payload_info(self.portal)
        with override_settings(DEBUG=False, PUBLIC_URL='http://example.org'), self.assertRaises(ValidationError):
            payload_info(self.portal)


class TagPortalConcurrencyTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Requires PostgreSQL row locks')
        self.user = get_user_model().objects.create_user('parallel-portal')
        wallet = Wallet.objects.create(user=self.user)
        self.tag = Tag.objects.create(wallet=wallet, uid='11223344')
        self.portal = TagPortal.objects.create(tag=self.tag)

    def test_parallel_activation_emits_one_transition(self):
        barrier = Barrier(2)
        def worker(_):
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                barrier.wait(timeout=10)
                return activate(self.portal.code, user).pk
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(worker, range(2))), [self.portal.pk]*2)
        self.assertEqual(Audit.objects.filter(event='tag_portal_activated').count(), 1)
        self.assertEqual(WalletEvent.objects.filter(kind='tag_portal_activated').count(), 1)

    def test_parallel_block_and_activation_never_leave_active_credential(self):
        from django.core.exceptions import PermissionDenied
        barrier = Barrier(2)
        def worker(action):
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                barrier.wait(timeout=10)
                try:
                    action(self.portal.code, user)
                except PermissionDenied:
                    if action is not activate:
                        raise
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(worker, (block, activate)))
        self.tag.refresh_from_db()
        self.portal.refresh_from_db()
        self.assertFalse(self.tag.active)
        self.assertFalse(self.portal.enabled)
        self.assertEqual(Journal.objects.count(), 0)
