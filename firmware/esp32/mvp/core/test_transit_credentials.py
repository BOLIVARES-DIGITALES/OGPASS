import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from .models import ExternalTransitBalanceSnapshot, ExternalTransitCredential, Tag, Wallet
from .transit_credentials import decrypt_reference


@override_settings(
    CREDENTIAL_ENCRYPTION_KEY='test-encryption-key-that-is-long-and-unique',
    CREDENTIAL_HMAC_KEY='test-hmac-key-that-is-different-and-long',
    MOVIRED_BALANCE_API_URL='',
    MOVIRED_BALANCE_API_TOKEN='',
)
class ExternalTransitCredentialTests(TestCase):
    consent_version = 'transit-v1-2026-09-30'

    def setUp(self):
        self.user = get_user_model().objects.create_user('transit-user', password='test-password-123')
        self.wallet = Wallet.objects.create(user=self.user)
        self.client.force_login(self.user)

    def create(self, issuer='RED', reference='115212457', consent=True):
        return self.client.post(
            '/api/transit/credentials/',
            data=json.dumps({
                'issuer': issuer,
                'reference': reference,
                'consent': consent,
                'consent_version': self.consent_version,
            }),
            content_type='application/json',
        )

    def test_reference_is_encrypted_and_declaration_is_idempotent(self):
        response = self.create()
        self.assertEqual(response.status_code, 201)
        credential = ExternalTransitCredential.objects.get()
        self.assertNotIn('115212457', credential.encrypted_reference)
        self.assertEqual(decrypt_reference(credential.encrypted_reference), '115212457')
        self.assertEqual(len(credential.reference_hmac), 64)
        self.assertEqual(self.create().status_code, 200)
        self.assertEqual(ExternalTransitCredential.objects.count(), 1)

    def test_consent_authentication_and_owner_isolation(self):
        self.assertEqual(self.create(consent=False).status_code, 400)
        anonymous = Client()
        self.assertEqual(anonymous.post('/api/transit/credentials/', data='{}', content_type='application/json').status_code, 401)
        self.create()
        other = get_user_model().objects.create_user('transit-other')
        Wallet.objects.create(user=other)
        self.client.force_login(other)
        self.assertEqual(self.create().status_code, 409)

    def test_red_without_authorized_api_never_returns_fake_balance(self):
        credential_id = self.create().json()['credential']['id']
        result = self.client.post(f'/api/transit/credentials/{credential_id}/balance/').json()
        self.assertEqual(result['status'], 'integration_required')
        self.assertIsNone(result['balance'])
        self.assertEqual(result['credential']['verification_status'], 'declared')
        snapshot = ExternalTransitBalanceSnapshot.objects.get()
        self.assertIsNone(snapshot.balance_amount)
        self.assertEqual(snapshot.currency, 'CLP')

    def test_og_card_is_verified_only_for_its_owner(self):
        Tag.objects.create(uid='04AB1234567890', card_number='115212457', wallet=self.wallet)
        credential_id = self.create('OG', '115212457').json()['credential']['id']
        result = self.client.post(f'/api/transit/credentials/{credential_id}/balance/').json()
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['balance'], 0)
        self.assertEqual(result['source'], 'Ledger OGPASS')
        self.assertEqual(result['credential']['verification_status'], 'verified')
        self.assertEqual(result['product_details']['red_metro']['integration_status'], 'not_linked')
        self.assertIsNone(result['product_details']['red_metro']['outstanding_balance'])
        self.assertEqual(result['product_details']['red_web3']['integration_status'], 'not_linked')
        self.assertEqual(result['product_details']['red_web3']['accounts'], [])
        self.assertIsNone(result['product_details']['red_web3']['credit_line_xlm'])

    def test_owner_can_revoke_and_other_user_cannot_access(self):
        credential_id = self.create().json()['credential']['id']
        response = self.client.post(f'/api/transit/credentials/{credential_id}/revoke/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['credential']['verification_status'], 'revoked')
        other = get_user_model().objects.create_user('revocation-other')
        Wallet.objects.create(user=other)
        self.client.force_login(other)
        self.assertEqual(self.client.post(f'/api/transit/credentials/{credential_id}/balance/').status_code, 404)

    def test_csrf_is_required_for_credential_write(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        csrf_client.get('/api/session/')
        self.assertEqual(csrf_client.post('/api/transit/credentials/', data='{}', content_type='application/json').status_code, 403)
