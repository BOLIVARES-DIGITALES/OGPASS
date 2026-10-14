import hashlib
import json
import uuid
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction
from django.test import TestCase, override_settings, Client
from core.models import Wallet, Reader, Tag, CardScan, Operation, Journal, WalletEvent
from core.cards import request_association, complete_association, record_scan
from backend.apps.credentials.normalizer import normalize
from backend.apps.credentials.models import NormalizedCredential
from backend.apps.credentials.services import sync_tag
from backend.apps.devices.models import OgpassDevice, HardwareEvent
from backend.apps.devices.services import record_hardware_event, device_for, heartbeat_device
from backend.apps.identity.services import identity_for
from backend.apps.identity import tag_payload


@override_settings(OGPASS_MODE='product')
class LaunchTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('launch-user', password='fixture-password-123')
        self.other = get_user_model().objects.create_user('launch-other')
        self.staff = get_user_model().objects.create_user('launch-staff', is_staff=True)
        self.wallet = Wallet.objects.create(user=self.user)
        self.reader = Reader.objects.create(name='RC522 lab', token_hash=hashlib.sha256(b'launch-fixture-reader').hexdigest(), amount=1000, cost=700)
        self.headers = {'HTTP_AUTHORIZATION': 'Bearer launch-fixture-reader'}
        self.client.force_login(self.user)

    def event(self, **changes):
        payload = {'event_id': str(uuid.uuid4()), 'reader': 'rc522', 'technology': 'NFC', 'protocol': 'ISO14443A', 'uid': '04:A1:B2:C3:D4:E5:F6', 'metadata': {'sak': 8, 'atqa': 4}}
        payload.update(changes)
        return payload

    def post_scan(self, payload):
        return self.client.post('/api/v1/credentials/scan/', json.dumps(payload), content_type='application/json', **self.headers)

    def test_identity_stable_and_private_id_never_exposed(self):
        first = self.client.get('/api/v1/me/').json()
        self.assertEqual(first, self.client.get('/api/v1/me/').json())
        identity = identity_for(self.user)
        self.assertNotEqual(identity.public_id, identity.private_id)
        self.assertNotIn('private_id', first)
        self.assertNotIn(str(identity.private_id), self.client.get('/').content.decode())
        self.assertContains(self.client.get('/'), str(identity.public_id))
        self.assertEqual(first['wallet_id'], self.wallet.pk)

    def test_normalization_is_namespaced_strict_and_capabilities_honest(self):
        data = normalize(self.event())
        self.assertEqual(data['uid'], '04A1B2C3D4E5F6')
        self.assertNotIn('WRITE', data['capabilities'])
        self.assertNotIn('AUTH', data['capabilities'])
        self.assertFalse(normalize(self.event(protocol='ISO15693'))['recognized'])
        for uid in ('', 'XYZ', '123456', '11'*33):
            with self.assertRaises(ValueError): normalize(self.event(uid=uid))
        with self.assertRaises(ValueError): normalize(self.event(metadata={'password': 'never-store'}))

    def test_read_only_duplicate_event_and_conflict(self):
        payload = self.event()
        self.assertEqual(self.post_scan(payload).status_code, 201)
        self.assertEqual(self.post_scan(payload).status_code, 200)
        self.assertEqual(HardwareEvent.objects.count(), 1)
        self.assertEqual(CardScan.objects.count(), 1)
        self.assertEqual(NormalizedCredential.objects.count(), 1)
        self.assertEqual(Operation.objects.count(), 0)
        self.assertEqual(Journal.objects.count(), 0)
        self.assertEqual(self.post_scan(dict(payload, uid='11223344')).status_code, 409)
        self.assertEqual(self.post_scan(self.event(purpose='payment')).status_code, 400)

    def test_assignment_uses_existing_fresh_scan_and_preserves_wallet(self):
        result = self.post_scan(self.event()).json()
        item = request_association(self.wallet, '123456789')
        self.client.force_login(self.staff)
        response = self.client.post('/api/v1/credentials/assign/', json.dumps({'request_id': item.pk, 'scan_key': result['event_id'], 'number': item.card_number}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        credential = NormalizedCredential.objects.get()
        self.assertEqual(credential.identity.wallet_id, self.wallet.pk)
        self.client.force_login(self.user)
        self.assertEqual(len(self.client.get('/api/v1/credentials/').json()['credentials']), 1)
        self.assertEqual(len(self.client.get('/api/v1/devices/').json()['devices']), 1)

    def test_users_cannot_claim_raw_uids_or_access_other_wallet_events(self):
        tag = Tag.objects.create(uid='04A1B2C3D4E5F6', wallet=self.wallet)
        sync_tag(tag)
        self.post_scan(self.event())
        self.client.force_login(self.other)
        for path, key in [('credentials/', 'credentials'), ('devices/', 'devices'), ('events/recent/', 'events')]:
            self.assertEqual(self.client.get('/api/v1/' + path).json()[key], [])
        self.assertEqual(self.client.post('/api/v1/credentials/assign/', '{}', content_type='application/json').status_code, 403)
        self.assertEqual(self.client.post('/api/v1/devices/register/', '{}', content_type='application/json').status_code, 403)

    def test_mode_does_not_grant_privileges_or_leak_raw_metadata(self):
        tag = Tag.objects.create(uid='04A1B2C3D4E5F6', wallet=self.wallet)
        sync_tag(tag); self.post_scan(self.event())
        with override_settings(OGPASS_MODE='developer'):
            self.assertNotIn('metadata', self.client.get('/api/v1/events/recent/').json()['events'][0])
            self.client.force_login(self.staff)
            self.assertIn('metadata', self.client.get('/api/v1/events/recent/').json()['events'][0])
        self.assertNotIn('metadata', self.client.get('/api/v1/events/recent/').json()['events'][0])

    def test_reader_auth_device_binding_and_disable(self):
        payload = self.event()
        self.assertEqual(self.client.post('/api/v1/credentials/scan/', json.dumps(payload), content_type='application/json').status_code, 401)
        self.assertEqual(self.post_scan(dict(payload, device_id=str(uuid.uuid4()))).status_code, 400)
        self.post_scan(payload)
        device = OgpassDevice.objects.get()
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(f'/api/v1/devices/{device.pk}/disable/').status_code, 200)
        self.assertEqual(self.post_scan(payload).status_code, 401)

    def test_optional_failure_does_not_mark_primary_offline(self):
        device = heartbeat_device(self.reader, {'firmware_version': 'test', 'health': {'rc522':'CONNECTED', 'pn532':'ERROR', 'ble':'DISABLED'}})
        self.client.force_login(self.staff)
        data = self.client.get('/api/v1/devices/').json()['devices'][0]
        self.assertEqual(data['status'], 'ONLINE')
        self.assertEqual(self.post_scan(self.event()).status_code, 201)

    def test_unknown_protocol_is_observable_without_wallet_link(self):
        response = self.post_scan(self.event(protocol='ISO15693'))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['status'], 'UNKNOWN_TECHNOLOGY')
        self.assertEqual(NormalizedCredential.objects.count(), 0)
        self.assertEqual(CardScan.objects.count(), 0)

    def test_transaction_rollback_removes_event_and_wallet_notification(self):
        tag = Tag.objects.create(uid='04A1B2C3D4E5F6', wallet=self.wallet)
        sync_tag(tag)
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                record_hardware_event(self.reader, self.event())
                raise RuntimeError('rollback')
        self.assertEqual(HardwareEvent.objects.count(), 0)
        self.assertEqual(WalletEvent.objects.count(), 0)
        from core.realtime import latest
        self.assertEqual(latest(0), 0)

    def test_existing_legacy_association_and_wallet_notification(self):
        scan = record_scan(self.reader, '04A1B2C3D4E5F6', uuid.uuid4())
        item = request_association(self.wallet, '123456789')
        complete_association(item.pk, scan.pk, item.card_number, self.staff.pk)
        self.assertEqual(NormalizedCredential.objects.get().identity.wallet_id, self.wallet.pk)
        before = WalletEvent.objects.count()
        self.post_scan(self.event())
        self.assertEqual(WalletEvent.objects.count(), before + 1)

    def test_signed_tag_reference_tampering_expiry_and_revocation(self):
        tag = Tag.objects.create(uid='11223344', wallet=self.wallet)
        credential = sync_tag(tag)
        payload = tag_payload.issue(credential)
        self.assertEqual(tag_payload.verify(payload).pk, credential.pk)
        data = signing.loads(payload, salt=tag_payload.SALT)
        self.assertNotIn('private_id', data)
        self.assertEqual(data['purpose'], 'profile_reference')
        with self.assertRaises(signing.BadSignature): tag_payload.verify(payload + 'x')
        with self.assertRaises(signing.SignatureExpired): tag_payload.verify(payload, max_age=-1)
        tag.active = False;tag.save(update_fields=['active'])
        with self.assertRaises(signing.BadSignature): tag_payload.verify(payload)

    def test_registration_csrf_auth_and_no_token_replay(self):
        self.client.force_login(self.staff)
        payload = {'name':'Node 2', 'driver':'rc522'}
        response = self.client.post('/api/v1/devices/register/', json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('reader_token', response.json())
        self.assertEqual(self.client.post('/api/v1/devices/register/', json.dumps(payload), content_type='application/json').status_code, 409)
        self.assertNotIn('reader_token', self.client.get('/api/v1/devices/').content.decode())
        csrf = Client(enforce_csrf_checks=True);csrf.force_login(self.staff)
        self.assertEqual(csrf.post('/api/v1/devices/register/', json.dumps(payload), content_type='application/json').status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get('/api/v1/me/').status_code, 401)
        self.assertEqual(self.client.get('/api/v1/health/').status_code, 200)

