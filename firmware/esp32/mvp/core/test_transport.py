from unittest.mock import Mock, patch
import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from .adapters import Transport
from .cards import request_association
from .models import Wallet, Tag, Journal


class TransportPortalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.wallet = Wallet.objects.create(user=get_user_model().objects.create_user('transport-owner'))
        self.other = Wallet.objects.create(user=get_user_model().objects.create_user('transport-other'))
        self.client.force_login(self.wallet.user)

    def test_number_alone_exposes_consultation_without_nfc_or_fake_balance(self):
        self.client.post('/tags/',{'card_number':'114309782'})
        request_association(self.other,'998877665')
        response = Mock(status_code=200,text='<input id="txtNumTarjeta"><input id="defaultReal"><script>realperson</script>')
        with patch('core.adapters.requests.get',return_value=response) as get:
            data = self.client.get('/api/transport/').json()
            self.assertEqual(data['status'],'verification_required')
            self.assertEqual(data['cards'],[{'card_number':'114309782','balance':None,'status':'verification_required'}])
            self.assertIsNone(data['balance'])
            self.assertIsNone(data['updated_at'])
            self.client.get('/api/transport/')
            get.assert_called_once_with(Transport.portal_url,timeout=(3,5),allow_redirects=False)
        self.assertFalse(Tag.objects.exists())
        self.assertFalse(Journal.objects.exists())

    def test_portal_failure_is_not_zero_and_does_not_block_ogpass(self):
        request_association(self.wallet,'114309782')
        with patch('core.adapters.requests.get',side_effect=requests.Timeout):
            data = self.client.get('/api/transport/').json()
        self.assertEqual(data['status'],'unavailable')
        self.assertIsNone(data['balance'])
        self.assertEqual(self.client.get('/api/state/').status_code,200)

    def test_no_card_no_external_request_and_anonymous_denied(self):
        with patch('core.adapters.requests.get') as get:
            self.assertEqual(self.client.get('/api/transport/').json()['status'],'no_card')
            get.assert_not_called()
        self.client.logout()
        self.assertEqual(self.client.get('/api/transport/').status_code,302)

    def test_changed_portal_or_redirect_cannot_be_reported_as_balance(self):
        request_association(self.wallet,'114309782')
        for response in [Mock(status_code=200,text='Maintenance'),Mock(status_code=302,text='')]:
            cache.clear()
            with patch('core.adapters.requests.get',return_value=response):
                data=self.client.get('/api/transport/').json()
                self.assertIn(data['status'],['integration_required','unavailable'])
                self.assertIsNone(data['balance'])
