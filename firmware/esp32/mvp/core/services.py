import re
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from .models import Wallet, Tag, Reader, Journal, Entry, TopUp, Operation, Audit
from .realtime import emit_event

class Conflict(ValueError): pass

def uid_normalize(raw):
    uid = re.sub(r'[: -]', '', str(raw)).upper()
    if len(uid) not in (8,14,20) or not re.fullmatch('[0-9A-F]+',uid):
        raise ValueError('UID ISO14443A inválido')
    return uid

def balance(wallet):
    return -(Entry.objects.filter(account=f'wallet:{wallet.pk}').aggregate(n=Sum('amount'))['n'] or 0)

def post(reference, kind, actor, lines, reversal_of=None):
    if sum(n for _, n in lines) != 0 or not lines: raise ValueError('Unbalanced journal')
    j = Journal.objects.create(reference=reference,kind=kind,actor=actor,reversal_of=reversal_of)
    Entry.objects.bulk_create([Entry(journal=j,account=a,amount=n) for a,n in lines if n])
    Audit.objects.create(actor=actor,event=kind,reference=reference,details={'journal':str(j.id)})
    for wallet_id in {int(a.split(':')[1]) for a,n in lines if a.startswith('wallet:')}:
        emit_event(wallet_id,kind)
    return j

@transaction.atomic
def bind_tag(wallet, uid):
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    uid = uid_normalize(uid)
    tag, created = Tag.objects.get_or_create(uid=uid, defaults={'wallet':wallet})
    if tag.wallet_id != wallet.pk: raise Conflict('Tag ya asociado a otra cuenta')
    if not tag.active: raise Conflict('Tag desactivado; contacte al administrador')
    if created: Audit.objects.create(actor=str(wallet.user_id), event='tag_bound',reference=uid)
    return tag

@transaction.atomic
def touch(reader, uid, key):
    reader = Reader.objects.select_for_update().get(pk=reader.pk)
    uid = uid_normalize(uid)
    existing = Operation.objects.filter(key=key).first()
    if existing:
        if existing.reader_id != reader.pk or existing.uid != uid: raise Conflict('Idempotency key conflict')
        return existing
    reader.last_seen = timezone.now()
    reader.last_uid = uid
    reader.save(update_fields=['last_seen','last_uid'])
    tag = Tag.objects.filter(uid=uid,active=True).first()
    op = Operation.objects.create(key=key,reader=reader,wallet=tag.wallet if tag else None,uid=uid,amount=reader.amount,cost=reader.cost,expires_at=timezone.now()+timedelta(seconds=90),status='pending' if tag else 'declined',reason='' if tag else 'unknown_tag')
    Audit.objects.create(actor=f'reader:{reader.pk}',event='touch',reference=str(op.pk),details={'status':op.status})
    if op.wallet_id: emit_event(op.wallet_id,'operation_pending')
    return op

@transaction.atomic
def decide(wallet, op_id, approve):
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    op = Operation.objects.select_for_update().get(pk=op_id,wallet=wallet)
    if op.status != 'pending': return op
    if timezone.now() > op.expires_at: op.status,op.reason = 'expired','confirmation_timeout'
    elif not approve: op.status,op.reason = 'declined','user_declined'
    elif wallet.frozen or not Tag.objects.filter(wallet=wallet,uid=op.uid,active=True).exists() or not Reader.objects.filter(pk=op.reader_id,active=True).exists():
        op.status,op.reason = 'declined','account_or_tag_disabled'
    elif balance(wallet) < op.amount: op.status,op.reason = 'declined','insufficient_balance'
    else:
        op.journal = post(f'operation:{op.pk}','operation',str(wallet.user_id),[(f'wallet:{wallet.pk}',op.amount),('revenue:operations',-op.amount),('expense:operations',op.cost),('liability:provider',-op.cost)])
        op.status = 'approved'
    op.save()
    Audit.objects.create(actor=str(wallet.user_id),event='operation_decision',reference=str(op.pk),details={'status':op.status,'reason':op.reason})
    emit_event(wallet.pk,'operation_decision')
    return op

@transaction.atomic
def reverse_operation(op_id, actor, reason):
    if not reason.strip(): raise ValueError('Motivo obligatorio')
    initial = Operation.objects.get(pk=op_id)
    Wallet.objects.select_for_update().get(pk=initial.wallet_id)
    op = Operation.objects.select_for_update().get(pk=op_id)
    if op.status == 'reversed': return op
    if op.status != 'approved': raise Conflict('Solo se puede reversar una operación aprobada')
    post(f'reversal:{op.pk}','reversal',actor,[(e.account,-e.amount) for e in op.journal.entries.all()],op.journal)
    op.status = 'reversed'
    op.save(update_fields=['status'])
    Audit.objects.create(actor=actor,event='reversal_reason',reference=str(op.pk),details={'reason':reason})
    return op

@transaction.atomic
def apply_payment(payment):
    # Only canonical data fetched from Mercado Pago; webhook body never credits money.
    from django.conf import settings
    if payment.get('live_mode') is not True: raise ValueError('Test payments cannot credit CLP')
    if str(payment.get('collector_id')) != settings.MP_COLLECTOR_ID: raise ValueError('Wrong collector')
    initial = TopUp.objects.get(pk=payment['external_reference'])
    wallet = Wallet.objects.select_for_update().get(pk=initial.wallet_id)
    topup = TopUp.objects.select_for_update().get(pk=initial.pk)
    if payment.get('currency_id') != 'CLP' or Decimal(str(payment['transaction_amount'])) != topup.amount:
        raise ValueError('Payment amount or currency mismatch')
    payment_id = str(payment['id'])
    if topup.payment_id and topup.payment_id != payment_id: raise Conflict('Multiple payments for one topup: reconcile manually')
    status = payment['status']
    refunded = Decimal(str(payment.get('transaction_amount_refunded',0)))
    if status in ('refunded','charged_back') or refunded > 0:
        # Refunds and chargebacks require reviewed reconciliation; never hide a deficit.
        wallet.frozen = True
        wallet.save(update_fields=['frozen'])
        topup.status = 'review_required'
        topup.save(update_fields=['status'])
        Audit.objects.create(actor='mercadopago',event='payment_dispute',reference=payment_id,details={'status':status,'refunded':str(refunded)})
        emit_event(wallet.pk,'payment_dispute')
        return topup
    if topup.journal_id: return topup
    if status != 'approved':
        topup.status = status
        topup.save(update_fields=['status'])
        emit_event(wallet.pk,'payment_status')
        return topup
    if not isinstance(payment.get('fee_details'), list): raise ValueError('Payment fee details unavailable')
    fee = sum((Decimal(str(f['amount'])) for f in payment['fee_details']), Decimal('0'))
    fee = int(fee.quantize(Decimal('1'),rounding=ROUND_CEILING))
    if fee < 0 or fee > topup.amount: raise ValueError('Invalid payment fee')
    topup.journal = post(f'payment:{payment_id}','topup','mercadopago',[('asset:mercadopago',topup.amount-fee),('expense:payments',fee),(f'wallet:{wallet.pk}',-topup.amount)])
    topup.fee,topup.status,topup.payment_id = fee,'credited',payment_id
    topup.save()
    return topup

def reconciliation():
    totals = dict(Entry.objects.values('account').annotate(total=Sum('amount')).values_list('account','total'))
    broken = list(Journal.objects.annotate(total=Sum('entries__amount')).exclude(total=0).values_list('reference',flat=True))
    revenue = -totals.get('revenue:operations',0)
    costs = totals.get('expense:operations',0)
    fees = totals.get('expense:payments',0)
    return {'revenue':revenue,'cost':costs,'fees':fees,'result':revenue-costs-fees,'trial_balance':sum(totals.values()),'unbalanced_journals':broken,'wallet_liability':-sum(n for a,n in totals.items() if a.startswith('wallet:')),'payment_receivable':totals.get('asset:mercadopago',0),'provider_payable':-totals.get('liability:provider',0),'preload_liability':-sum(n for a,n in totals.items() if a.startswith('preload:'))}

@transaction.atomic
def expire_operations():
    for op in Operation.objects.select_for_update().filter(status='pending',expires_at__lt=timezone.now())[:100]:
        op.status,op.reason='expired','confirmation_timeout'
        op.save(update_fields=['status','reason'])
        Audit.objects.create(actor='system',event='operation_expired',reference=str(op.pk))
        if op.wallet_id: emit_event(op.wallet_id,'operation_expired')
