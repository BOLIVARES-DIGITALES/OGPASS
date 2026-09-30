import hashlib,hmac,json,time,uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from datetime import timedelta
from django.test import TestCase,TransactionTestCase,override_settings
from django.contrib.auth import get_user_model
from django.db import connection,transaction,IntegrityError,DatabaseError,connections
from django.utils import timezone
from .models import Wallet,Tag,Reader,TopUp,Operation,Journal,Entry,Audit,StellarAccount
from .services import bind_tag,balance,touch,decide,apply_payment,reverse_operation,reconciliation,Conflict

@override_settings(MP_COLLECTOR_ID='123')
class FlowTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('ana',password='secure-test-only-123')
        self.wallet=Wallet.objects.create(user=self.user)
        self.reader=Reader.objects.create(name='ESP32-001',token_hash=hashlib.sha256(b'test-token').hexdigest(),amount=1000,cost=700)
        bind_tag(self.wallet,'04:AB:12:34:56:78:90')
        self.t=TopUp.objects.create(wallet=self.wallet,amount=5000,key=uuid.uuid4())
        self.payment={'id':9001,'external_reference':str(self.t.pk),'live_mode':True,'collector_id':123,'currency_id':'CLP','transaction_amount':5000,'status':'approved','fee_details':[{'amount':100}]}
    def fund(self):return apply_payment(self.payment)
    def operation(self):return touch(self.reader,'04AB1234567890',uuid.uuid4())
    def test_full_flow_and_reversal(self):
        self.assertEqual(balance(self.wallet),0)
        self.fund();self.assertEqual(balance(self.wallet),5000)
        op=self.operation();self.assertEqual(balance(self.wallet),5000)
        result=decide(self.wallet,op.pk,True)
        self.assertEqual(result.status,'approved');self.assertEqual(balance(self.wallet),4000)
        report=reconciliation();self.assertEqual(report['result'],200);self.assertEqual(report['trial_balance'],0)
        decide(self.wallet,op.pk,True);self.assertEqual(balance(self.wallet),4000)
        reverse_operation(op.pk,'admin','Servicio no prestado');self.assertEqual(balance(self.wallet),5000)
        reverse_operation(op.pk,'admin','Reintento');self.assertEqual(Journal.objects.filter(kind='reversal').count(),1)
        self.assertEqual(reconciliation()['result'],-100)
    def test_zero_fee_payment(self):
        apply_payment({**self.payment,'fee_details':[]})
        self.assertEqual(balance(self.wallet),5000)
        self.assertEqual(reconciliation()['fees'],0)
    def test_unknown_fee_not_assumed_free(self):
        payment=dict(self.payment);payment.pop('fee_details')
        with self.assertRaises(ValueError):apply_payment(payment)
    def test_registration_rate_limited(self):
        for _ in range(5):self.client.post('/register/',{})
        self.assertEqual(self.client.post('/register/',{}).status_code,429)
    def test_payment_idempotent(self):
        self.fund();self.fund();self.assertEqual(balance(self.wallet),5000)
        self.assertEqual(Journal.objects.filter(kind='topup').count(),1)
    def test_touch_idempotent(self):
        op=self.operation();self.assertEqual(touch(self.reader,op.uid,op.key).pk,op.pk)
        with self.assertRaises(Conflict):touch(self.reader,'11223344',op.key)
    def test_insufficient_is_recorded(self):
        op=decide(self.wallet,self.operation().pk,True)
        self.assertEqual(op.reason,'insufficient_balance');self.assertEqual(balance(self.wallet),0)
        self.assertTrue(Audit.objects.filter(event='operation_decision').exists())
    def test_unknown_tag(self):self.assertEqual(touch(self.reader,'11223344',uuid.uuid4()).status,'declined')
    def test_expiration(self):
        self.fund();op=self.operation();op.expires_at=timezone.now()-timedelta(seconds=1);op.save()
        self.assertEqual(decide(self.wallet,op.pk,True).status,'expired');self.assertEqual(balance(self.wallet),5000)
    def test_user_declines(self):
        self.fund();self.assertEqual(decide(self.wallet,self.operation().pk,False).reason,'user_declined')
    def test_frozen_wallet(self):
        self.fund();self.wallet.frozen=True;self.wallet.save()
        self.assertEqual(decide(self.wallet,self.operation().pk,True).reason,'account_or_tag_disabled')
    def test_disabled_tag(self):
        self.fund();op=self.operation();Tag.objects.update(active=False)
        self.assertEqual(decide(self.wallet,op.pk,True).reason,'account_or_tag_disabled')
    def test_payment_rejects_wrong_source(self):
        for field,value in [('live_mode',False),('collector_id',999),('currency_id','USD'),('transaction_amount',5001)]:
            with self.subTest(field=field):
                with self.assertRaises(ValueError): apply_payment({**self.payment,field:value})
        self.assertEqual(balance(self.wallet),0)
    def test_pending_payment_not_credited(self):
        apply_payment({**self.payment,'status':'pending'});self.assertEqual(balance(self.wallet),0)
    def test_dispute_freezes_and_alerts(self):
        self.fund();apply_payment({**self.payment,'status':'charged_back'})
        self.wallet.refresh_from_db();self.assertTrue(self.wallet.frozen)
        self.t.refresh_from_db();self.assertEqual(self.t.status,'review_required')
    def test_unique_provider_payment(self):
        self.fund();other=TopUp.objects.create(wallet=self.wallet,amount=5000,key=uuid.uuid4())
        with self.assertRaises(IntegrityError):apply_payment({**self.payment,'external_reference':str(other.pk)})
        self.assertEqual(balance(self.wallet),5000)
    def test_other_wallet_cannot_confirm_or_reassign(self):
        other=Wallet.objects.create(user=get_user_model().objects.create_user('other'))
        with self.assertRaises(Conflict):bind_tag(other,'04AB1234567890')
        self.client.force_login(other.user)
        self.assertEqual(self.client.post(f'/api/operations/{self.operation().pk}/confirm/',data='{"approve":true}',content_type='application/json').status_code,404)
    def test_session_required(self):
        self.assertEqual(self.client.get('/api/state/').status_code,302)
        self.client.force_login(self.user);self.assertEqual(self.client.get('/ops/').status_code,302)
    def test_csrf_required(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(f'/api/operations/{self.operation().pk}/confirm/',data='{"approve":true}',content_type='application/json').status_code,403)
    def test_reader_api(self):
        data={'uid':'04AB1234567890','key':str(uuid.uuid4()),'amount':1}
        self.assertEqual(self.client.post('/api/reader/touch/',data=json.dumps(data),content_type='application/json').status_code,401)
        r=self.client.post('/api/reader/touch/',data=json.dumps(data),content_type='application/json',HTTP_AUTHORIZATION='Bearer test-token')
        self.assertEqual(r.status_code,200);self.assertEqual(r.json()['amount'],1000)
        self.assertEqual(r.json()['status'],'pending')
    def test_html_views(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/'),'Fondos OGPASS')
        self.assertEqual(self.client.get('/api/state/').json()['balance'],0)
        self.user.is_staff=True;self.user.save()
        self.assertContains(self.client.get('/ops/'),'Resultado acumulado')
    @patch('core.views.Stellar.balance',return_value={'status':'unfunded','network':'testnet','address':'GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF','balances':[]})
    def test_client_can_link_public_stellar_account_without_secret(self,_balance):
        from stellar_sdk import Keypair
        self.client.force_login(self.user)
        payload={'network':'testnet','address':Keypair.random().public_key}
        response=self.client.post('/api/stellar/accounts/',data=json.dumps(payload),content_type='application/json')
        self.assertEqual(response.status_code,201)
        self.assertTrue(StellarAccount.objects.filter(wallet=self.wallet,network='testnet',address=payload['address']).exists())
        self.assertEqual(self.client.post('/api/stellar/accounts/',data=json.dumps(payload),content_type='application/json').status_code,200)
        response=self.client.post('/api/stellar/accounts/',data=json.dumps({'network':'testnet','address':Keypair.random().public_key}),content_type='application/json')
        self.assertEqual(response.status_code,409)
    def test_client_cannot_link_stellar_secret_or_bad_network(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post('/api/stellar/accounts/',data=json.dumps({'network':'mainnet','address':'SAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'}),content_type='application/json').status_code,400)
        self.assertEqual(self.client.post('/api/stellar/accounts/',data=json.dumps({'network':'future','address':'GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF'}),content_type='application/json').status_code,400)
    @override_settings(PAYMENTS_ENABLED=False)
    def test_unconnected_payments_disabled(self):
        self.client.force_login(self.user)
        self.client.post('/topups/',{'amount':1000,'key':str(uuid.uuid4())})
        self.assertEqual(TopUp.objects.count(),1)
    @override_settings(PAYMENTS_ENABLED=True,MP_WEBHOOK_SECRET='test-secret')
    def test_signed_webhook_credits_only_canonical_payment(self):
        ts=str(int(time.time()));manifest=f'id:9001;request-id:test-request;ts:{ts};'
        sig=hmac.new(b'test-secret',manifest.encode(),hashlib.sha256).hexdigest()
        headers={'HTTP_X_SIGNATURE':f'ts={ts},v1={sig}','HTTP_X_REQUEST_ID':'test-request'}
        body=json.dumps({'type':'payment','data':{'id':'9001'},'amount':999999})
        with patch('core.adapters.MercadoPago.payment',return_value=self.payment):
            for _ in range(2):self.assertEqual(self.client.post('/api/payments/webhook/?data.id=9001',data=body,content_type='application/json',**headers).status_code,200)
        self.assertEqual(balance(self.wallet),5000)
        headers['HTTP_X_SIGNATURE']='ts=0,v1=invalid'
        self.assertEqual(self.client.post('/api/payments/webhook/?data.id=9001',data=body,content_type='application/json',**headers).status_code,401)
    def test_invalid_uid(self):
        with self.assertRaises(ValueError):bind_tag(self.wallet,'bad')

@override_settings(MP_COLLECTOR_ID='123')
class PostgresConcurrencyTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor!='postgresql':self.skipTest('Requires PostgreSQL; SQLite does not implement row locks')
        user=get_user_model().objects.create_user('parallel')
        self.wallet=Wallet.objects.create(user=user)
        self.reader=Reader.objects.create(name='parallel',amount=1000,cost=700,token_hash='unused')
        bind_tag(self.wallet,'11223344')
        t=TopUp.objects.create(wallet=self.wallet,amount=1000,key=uuid.uuid4())
        apply_payment({'id':1,'external_reference':str(t.pk),'live_mode':True,'collector_id':123,'currency_id':'CLP','transaction_amount':1000,'status':'approved','fee_details':[]})
    def test_two_parallel_debits_never_overdraw(self):
        ids=[touch(self.reader,'11223344',uuid.uuid4()).pk for _ in range(2)]
        def debit(pk):
            try:return decide(self.wallet,pk,True).status
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(debit,ids))
        self.assertCountEqual(results,['approved','declined']);self.assertEqual(balance(self.wallet),0)
    def test_database_rejects_unbalanced_and_mutation(self):
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                j=Journal.objects.create(reference='invalid',kind='test',actor='test')
                Entry.objects.create(journal=j,account='bad',amount=100)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():Entry.objects.all().update(amount=1)

    def test_committed_journal_cannot_receive_new_entries(self):
        j=Journal.objects.first()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                Entry.objects.bulk_create([Entry(journal=j,account='bad',amount=100),Entry(journal=j,account='other',amount=-100)])

    def test_parallel_preload_activation_is_single_credit(self):
        from .preloads import issue_preload,activate_preload
        self.wallet.user.is_staff=True;self.wallet.user.save()
        recipient=Wallet.objects.create(user=get_user_model().objects.create_user('preload-recipient'))
        preload=issue_preload(self.wallet,recipient,1000,uuid.uuid4())
        def activate(_):
            try:return activate_preload(recipient,preload.pk).status
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(activate,range(2)))
        self.assertEqual(statuses,['activated','activated'])
        self.assertEqual(balance(recipient),1000)
        self.assertEqual(balance(self.wallet),0)
        self.assertEqual(Journal.objects.filter(kind='preload_activate').count(),1)

    def test_parallel_preload_reservations_cannot_overdraw(self):
        from .preloads import issue_preload
        self.wallet.user.is_staff=True;self.wallet.user.save()
        recipient=Wallet.objects.create(user=get_user_model().objects.create_user('reserve-recipient'))
        def reserve(_):
            try:
                issue_preload(self.wallet,recipient,1000,uuid.uuid4());return 'reserved'
            except ValueError:return 'insufficient'
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(reserve,range(2)))
        self.assertCountEqual(statuses,['reserved','insufficient'])
        self.assertEqual(balance(self.wallet),0)
        self.assertEqual(reconciliation()['preload_liability'],1000)


@override_settings(MP_COLLECTOR_ID='123')
class CardsAndPreloadsTests(TestCase):
    def setUp(self):
        from .models import CardScan, Preload, WalletEvent
        self.user=get_user_model().objects.create_user('card-user')
        self.wallet=Wallet.objects.create(user=self.user)
        self.admin_user=get_user_model().objects.create_user('funding-admin',is_staff=True)
        self.issuer=Wallet.objects.create(user=self.admin_user)
        self.reader=Reader.objects.create(name='reader-test',token_hash=hashlib.sha256(b'card-reader-token').hexdigest())
        self.uid='04AB1234567890'
    def scan(self,uid=None,purpose='balance'):
        from .cards import record_scan
        return record_scan(self.reader,uid or self.uid,uuid.uuid4(),purpose)
    def pair(self,wallet=None,uid=None,number='114309782',replace=None):
        from .cards import associate_scan,pairing_code
        scan=self.scan(uid)
        return associate_scan(wallet or self.wallet,number,pairing_code(scan),replace)
    def fund(self,wallet,amount=5000):
        t=TopUp.objects.create(wallet=wallet,amount=amount,key=uuid.uuid4())
        return apply_payment({'id':str(uuid.uuid4().int),'external_reference':str(t.pk),'live_mode':True,'collector_id':123,'currency_id':'CLP','transaction_amount':amount,'status':'approved','fee_details':[]})
    def test_number_is_not_uid_and_does_not_associate_without_scan(self):
        self.client.force_login(self.user)
        self.client.post('/tags/',{'card_number':'114309782','consent':'yes'})
        self.assertFalse(Tag.objects.exists())
        from .cards import record_scan
        with self.assertRaises(ValueError):record_scan(self.reader,'114309782',uuid.uuid4())
    def test_pairing_and_balance_query_never_debit(self):
        from .cards import scan_data
        tag=self.pair();self.assertEqual(tag.card_number,'114309782')
        self.fund(self.wallet)
        result=scan_data(self.scan())
        self.assertEqual(result['status'],'balance');self.assertEqual(result['available_balance'],5000)
        self.assertEqual(result['source'],'Ledger OGPASS · CLP')
        self.assertEqual(result['transport']['balance'],None)
        self.assertEqual(Operation.objects.count(),0)
        self.assertEqual(balance(self.wallet),5000)
    def test_scan_retry_returns_current_balance(self):
        from .cards import record_scan,scan_data
        self.pair();scan=self.scan()
        self.assertEqual(scan_data(scan)['balance'],0)
        self.fund(self.wallet)
        retry=record_scan(self.reader,self.uid,scan.key)
        self.assertEqual(scan_data(retry)['balance'],5000)
        with self.assertRaises(Conflict):record_scan(self.reader,self.uid,scan.key,'payment')
    def test_pairing_expires_and_is_not_reusable_by_other_user(self):
        from .cards import associate_scan,pairing_code
        scan=self.scan();code=pairing_code(scan)
        scan.expires_at=timezone.now()-timedelta(seconds=1);scan.save()
        with self.assertRaises(ValueError):associate_scan(self.wallet,'114309782',code)
        scan=self.scan();code=pairing_code(scan)
        first=associate_scan(self.wallet,'114309782',code)
        self.assertEqual(associate_scan(self.wallet,'114309782',code).pk,first.pk)
        with self.assertRaises(Conflict):associate_scan(self.issuer,'999999999',code)
    def test_replace_keeps_wallet_and_preloads_and_disables_old_tag(self):
        from .preloads import issue_preload,activate_preload
        old=self.pair();self.fund(self.issuer)
        p=issue_preload(self.issuer,self.wallet,1000,uuid.uuid4())
        new=self.pair(uid='041234567890AB',number='998877665',replace=old.pk)
        old.refresh_from_db();self.assertFalse(old.active)
        self.assertEqual(new.wallet_id,self.wallet.pk)
        activate_preload(self.wallet,p.pk)
        self.assertEqual(balance(self.wallet),1000)
        from .cards import scan_data
        self.assertEqual(scan_data(self.scan())['status'],'disabled')
        self.assertEqual(scan_data(self.scan(new.uid))['available_balance'],1000)
    def test_cannot_replace_another_users_card(self):
        from .cards import associate_scan,pairing_code
        other=self.pair(wallet=self.issuer)
        scan=self.scan('041234567890AB')
        with self.assertRaises(ValueError):associate_scan(self.wallet,'998877665',pairing_code(scan),other.pk)
        other.refresh_from_db();self.assertTrue(other.active)
    def test_balance_hidden_for_disabled_card_and_zero_available_if_frozen(self):
        from .cards import scan_data
        tag=self.pair();self.fund(self.wallet);self.wallet.frozen=True;self.wallet.save()
        self.assertEqual(scan_data(self.scan())['available_balance'],0)
        tag.active=False;tag.save();data=scan_data(self.scan(),True)
        self.assertEqual(data['balance'],None);self.assertNotIn('pairing_code',data)
    def test_reader_auth_and_wallet_isolation(self):
        payload={'uid':self.uid,'key':str(uuid.uuid4())}
        self.assertEqual(self.client.post('/api/reader/scans/',data=json.dumps(payload),content_type='application/json').status_code,401)
        response=self.client.post('/api/reader/scans/',data=json.dumps(payload),content_type='application/json',HTTP_AUTHORIZATION='Bearer card-reader-token')
        self.assertEqual(response.json()['status'],'pairing_required')
        self.assertEqual(response['Cache-Control'],'no-store')
        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.get('/api/state/').json()['last_scan'],None)
    def test_preload_requires_backing_and_staff(self):
        from .preloads import issue_preload
        with self.assertRaises(ValueError):issue_preload(self.issuer,self.wallet,1000,uuid.uuid4())
        self.fund(self.wallet)
        with self.assertRaises(ValueError):issue_preload(self.wallet,self.issuer,1000,uuid.uuid4())
        self.assertEqual(balance(self.wallet),5000)
    def test_preload_reserves_then_activates_once_without_expiry(self):
        from .preloads import issue_preload,activate_preload
        from .models import Preload
        self.fund(self.issuer);key=uuid.uuid4()
        p=issue_preload(self.issuer,self.wallet,1000,key)
        self.assertEqual(issue_preload(self.issuer,self.wallet,1000,key).pk,p.pk)
        self.assertEqual(balance(self.issuer),4000);self.assertEqual(balance(self.wallet),0)
        self.assertEqual(reconciliation()['preload_liability'],1000)
        Preload.objects.filter(pk=p.pk).update(created_at=timezone.now()-timedelta(days=3650))
        activate_preload(self.wallet,p.pk);activate_preload(self.wallet,p.pk)
        self.assertEqual(balance(self.wallet),1000)
        self.assertEqual(reconciliation()['preload_liability'],0)
        self.assertEqual(reconciliation()['trial_balance'],0)
    def test_preload_cancel_refunds_once_and_cannot_activate(self):
        from .preloads import issue_preload,cancel_preload,activate_preload
        self.fund(self.issuer);p=issue_preload(self.issuer,self.wallet,1000,uuid.uuid4())
        cancel_preload(self.issuer,p.pk);cancel_preload(self.issuer,p.pk)
        self.assertEqual(balance(self.issuer),5000)
        with self.assertRaises(Conflict):activate_preload(self.wallet,p.pk)
    def test_other_user_cannot_activate_and_cancel_after_activation_fails(self):
        from .preloads import issue_preload,activate_preload,cancel_preload
        self.fund(self.issuer);p=issue_preload(self.issuer,self.wallet,1000,uuid.uuid4())
        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.post(f'/api/preloads/{p.pk}/activate/').status_code,404)
        activate_preload(self.wallet,p.pk)
        with self.assertRaises(Conflict):cancel_preload(self.issuer,p.pk)
    def test_wallet_events_rollback_with_financial_changes(self):
        from .models import WalletEvent
        from .realtime import emit_event,latest
        try:
            with transaction.atomic():
                emit_event(self.wallet.pk,'will_rollback')
                raise ValueError('rollback')
        except ValueError:pass
        self.assertEqual(latest(self.wallet.pk),0)
        self.fund(self.wallet)
        self.assertTrue(WalletEvent.objects.filter(wallet=self.wallet,kind='topup').exists())
        self.assertEqual(latest(self.issuer.pk),0)
    def test_sse_auth_and_initial_private_refresh(self):
        self.assertEqual(self.client.get('/api/events/').status_code,302)
        self.client.force_login(self.user)
        response=self.client.get('/api/events/')
        self.assertEqual(response['Content-Type'],'text/event-stream')
        iterator=iter(response.streaming_content)
        self.assertIn(b'event: wallet',next(iterator))
        # Close only the generator: request_finished would close TestCase's outer transaction.
        response._iterator.close()

    def test_preload_cannot_activate_when_funding_account_is_frozen(self):
        from .preloads import issue_preload,activate_preload
        self.fund(self.issuer);p=issue_preload(self.issuer,self.wallet,1000,uuid.uuid4())
        self.issuer.frozen=True;self.issuer.save()
        with self.assertRaises(ValueError):activate_preload(self.wallet,p.pk)
        self.assertEqual(balance(self.wallet),0)

    def test_ops_stream_and_balances_require_staff(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/api/ops/events/').status_code,302)
        self.assertEqual(self.client.get('/api/ops/state/').status_code,302)
        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.get('/api/ops/state/').status_code,200)


class SimpleCardAssociationTests(TestCase):
    def setUp(self):
        from .models import CardAssociationRequest
        self.user = get_user_model().objects.create_user('simple-user')
        self.wallet = Wallet.objects.create(user=self.user)
        self.staff = get_user_model().objects.create_user('simple-staff',is_staff=True)
        self.reader = Reader.objects.create(name='Simple-reader',token_hash=hashlib.sha256(b'simple-token').hexdigest(),amount=1000,cost=700)
    def test_number_only_is_pending_and_strictly_nine_digits(self):
        from .models import CardAssociationRequest
        self.client.force_login(self.user)
        self.client.post('/tags/',{'card_number':'12345678'})
        self.assertFalse(CardAssociationRequest.objects.exists())
        self.client.post('/tags/',{'card_number':'114309782'})
        self.client.post('/tags/',{'card_number':'114309782'})
        self.assertEqual(CardAssociationRequest.objects.count(),1)
        self.assertFalse(Tag.objects.exists())
        self.assertEqual(self.client.get('/api/state/').json()['association_pending'],['114309782'])
        self.assertEqual(self.client.get('/api/ops/readers/').status_code,302)
        self.assertEqual(self.client.post('/ops/cards/associate/',{}).status_code,302)
    def test_staff_binds_explicit_scan_and_retry_is_idempotent(self):
        from .cards import request_association,record_scan
        request = request_association(self.wallet,'114309782')
        scan = record_scan(self.reader,'04AB1234567890',uuid.uuid4())
        self.client.force_login(self.staff)
        panel = self.client.get('/api/ops/readers/').json()
        self.assertTrue(panel['readers'][0]['online'])
        self.assertFalse(panel['readers'][0]['write_supported'])
        data = {'request_id':request.pk,'scan_key':scan.pk,'number':'114309782'}
        self.assertEqual(self.client.post('/ops/cards/associate/',data).status_code,200)
        self.assertEqual(self.client.post('/ops/cards/associate/',data).status_code,200)
        self.assertEqual(Tag.objects.get().wallet,self.wallet)
        self.assertFalse(Journal.objects.exists())
        panel = self.client.get('/api/ops/readers/').json()
        self.assertEqual(panel['readers'][0]['scan']['card_number'],'114309782')
        self.assertEqual(panel['requests'],[])
    def test_stale_changed_and_expired_scan_are_rejected(self):
        from .cards import request_association,record_scan,complete_association
        from .models import CardScan
        item = request_association(self.wallet,'114309782')
        scan = record_scan(self.reader,'04AB1234567890',uuid.uuid4())
        with self.assertRaises(ValueError):complete_association(item.pk,scan.pk,'999999999',self.staff.pk)
        newer = record_scan(self.reader,'04AB1234567891',uuid.uuid4())
        with self.assertRaises(ValueError):complete_association(item.pk,scan.pk,item.card_number,self.staff.pk)
        CardScan.objects.filter(pk=newer.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(ValueError):complete_association(item.pk,newer.pk,item.card_number,self.staff.pk)
        self.assertFalse(Tag.objects.exists())
    def test_offline_reader_does_not_claim_online(self):
        from .cards import request_association,record_scan,complete_association
        item = request_association(self.wallet,'114309782')
        scan = record_scan(self.reader,'04AB1234567890',uuid.uuid4())
        Reader.objects.filter(pk=self.reader.pk).update(last_seen=timezone.now()-timedelta(seconds=46))
        self.client.force_login(self.staff)
        self.assertFalse(self.client.get('/api/ops/readers/').json()['readers'][0]['online'])
        with self.assertRaises(ValueError):complete_association(item.pk,scan.pk,item.card_number,self.staff.pk)
