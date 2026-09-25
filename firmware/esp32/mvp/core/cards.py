"""Physical scan pairing and read-only balance queries; printed numbers are labels."""
import hashlib
import hmac
import re
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import CardScan, Reader, Wallet, Tag, Audit
from .services import Conflict, uid_normalize, bind_tag, touch, balance
from .realtime import emit_event


def card_number_normalize(raw):
    number = str(raw).strip().replace(' ', '').replace('-', '')
    if not re.fullmatch(r'[0-9]{4,12}', number):
        raise ValueError('Introduce entre 4 y 12 dígitos del número impreso, sin usar el UID ni datos bancarios.')
    return number


def pairing_code(scan):
    # Reproducible for a reader retry, stored only as a hash and expires in 3 minutes.
    return hmac.new(settings.SECRET_KEY.encode(),('ogpass-pair:'+str(scan.key)).encode(),hashlib.sha256).hexdigest()[:10].upper()


@transaction.atomic
def record_scan(reader, uid, key, purpose='balance'):
    if purpose not in ('balance','payment'):
        raise ValueError('Modo de lectura inválido')
    uid = uid_normalize(uid)
    reader = Reader.objects.select_for_update().get(pk=reader.pk,active=True)
    existing = CardScan.objects.filter(key=key).first()
    if existing:
        if existing.reader_id != reader.pk or existing.uid != uid or existing.purpose != purpose:
            raise Conflict('La referencia ya corresponde a otra lectura')
        return existing
    now = timezone.now()
    reader.last_seen, reader.last_uid = now, uid
    reader.save(update_fields=['last_seen','last_uid'])
    tag = Tag.objects.filter(uid=uid).first()
    scan = CardScan(key=key,reader=reader,uid=uid,purpose=purpose,expires_at=now+timedelta(minutes=3))
    if tag:
        scan.wallet = tag.wallet
        if purpose == 'payment' and tag.active:
            scan.operation = touch(reader,uid,key)
    else:
        scan.pairing_hash = hashlib.sha256(pairing_code(scan).encode()).hexdigest()
    scan.save()
    Audit.objects.create(actor=f'reader:{reader.pk}',event='card_scanned',reference=str(key),details={'purpose':purpose,'known':bool(tag)})
    if scan.wallet_id: emit_event(scan.wallet_id,'card_scanned')
    return scan


@transaction.atomic
def associate_scan(wallet, number, code, replace_tag_id=None):
    number = card_number_normalize(number)
    code = str(code).replace(' ','').replace('-','').strip().upper()
    if not re.fullmatch(r'[0-9A-F]{10}',code):
        raise ValueError('Introduce el código de 10 caracteres mostrado por el lector.')
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    scan = CardScan.objects.select_for_update().filter(pairing_hash=hashlib.sha256(code.encode()).hexdigest()).first()
    if not scan:
        raise ValueError('Código incorrecto. Comprueba el monitor del lector.')
    if scan.paired_at:
        tag = Tag.objects.filter(uid=scan.uid,wallet=wallet,card_number=number,active=True).first()
        if scan.wallet_id == wallet.pk and tag:
            return tag
        raise Conflict('Este código ya fue utilizado.')
    if scan.expires_at < timezone.now():
        raise ValueError('El código expiró. Retira la tarjeta y vuelve a escanearla.')
    if not Reader.objects.filter(pk=scan.reader_id,active=True).exists():
        raise ValueError('El lector ya no está habilitado.')
    if Tag.objects.filter(wallet=wallet,card_number=number).exclude(uid=scan.uid).exists():
        raise Conflict('Ya tienes otra tarjeta asociada con ese número.')
    previous = None
    if replace_tag_id:
        previous = Tag.objects.select_for_update().filter(pk=replace_tag_id,wallet=wallet,active=True).first()
        if previous is None: raise ValueError('La tarjeta a reemplazar no pertenece a tu cuenta o ya está desactivada.')
        if previous.uid == scan.uid: raise ValueError('Acerca una tarjeta distinta para reemplazar la anterior.')
    tag = bind_tag(wallet,scan.uid)
    tag.card_number = number
    tag.save(update_fields=['card_number'])
    if previous:
        previous.active = False
        previous.save(update_fields=['active'])
        Audit.objects.create(actor=str(wallet.user_id),event='card_replaced',reference=str(tag.pk),details={'previous_tag':previous.pk})
    scan.wallet,scan.paired_at = wallet,timezone.now()
    scan.save(update_fields=['wallet','paired_at'])
    Audit.objects.create(actor=str(wallet.user_id),event='card_paired',reference=str(scan.key),details={'tag':tag.pk,'card_number':number})
    emit_event(wallet.pk,'card_paired')
    return tag


def scan_data(scan, include_pairing=False):
    """Never returns a cached monetary snapshot: each query reads the ledger."""
    now = timezone.now()
    data = {'key':str(scan.key),'status':'unknown_card','reader':scan.reader.name,
            'purpose':scan.purpose,'scanned_at':scan.created_at.isoformat(),
            'expires_at':scan.expires_at.isoformat(),'balance':None,'available_balance':None,
            'currency':'CLP','source':'Ledger OGPASS · CLP','updated_at':now.isoformat(),
            'transport':{'status':'not_connected','balance':None}}
    if not scan.wallet_id:
        if scan.expires_at < now:
            data['status'] = 'expired'
        elif include_pairing:
            data['status'] = 'pairing_required'
            data['pairing_code'] = pairing_code(scan)
        return data
    tag = Tag.objects.filter(uid=scan.uid,wallet_id=scan.wallet_id).first()
    if not tag or not tag.active:
        data['status'] = 'disabled'
        return data
    wallet = Wallet.objects.get(pk=scan.wallet_id)
    funds = balance(wallet)
    data.update(status='balance',card_number=tag.card_number,balance=funds,
                available_balance=0 if wallet.frozen else max(0,funds),frozen=wallet.frozen)
    if wallet.frozen:
        data['status'] = 'frozen'
    if scan.operation_id:
        from .views import op_data
        data.update(op_data(scan.operation))
    return data


@transaction.atomic
def request_association(wallet, number):
    from .models import CardAssociationRequest
    if not re.fullmatch(r'[0-9]{9}', str(number).strip()):
        raise ValueError('Introduce exactamente nueve dígitos.')
    number = str(number).strip()
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    if Tag.objects.filter(wallet=wallet,card_number=number,active=True).exists():
        raise ValueError('Esta tarjeta ya está asociada a tu cuenta.')
    item = CardAssociationRequest.objects.filter(wallet=wallet,status='pending').first()
    if item:
        item.card_number = number
        item.save(update_fields=['card_number'])
    else:
        item = CardAssociationRequest.objects.create(wallet=wallet,card_number=number)
    Audit.objects.create(actor=str(wallet.user_id),event='card_association_requested',reference=str(item.pk),details={'card_number':number})
    emit_event(wallet.pk,'card_requested')
    return item


@transaction.atomic
def complete_association(request_id, scan_key, expected_number, actor):
    from .models import CardAssociationRequest
    # Same lock order as request_association; never bind the globally latest scan implicitly.
    item = CardAssociationRequest.objects.get(pk=request_id)
    wallet = Wallet.objects.select_for_update().get(pk=item.wallet_id)
    item = CardAssociationRequest.objects.select_for_update().get(pk=request_id)
    if item.card_number != expected_number:
        raise ValueError('La solicitud cambió. Actualiza y comprueba el número.')
    if item.status == 'completed':
        return item.tag
    scan = CardScan.objects.select_for_update().select_related('reader').get(pk=scan_key)
    if not scan.reader.active or not scan.reader.last_seen or (timezone.now()-scan.reader.last_seen).total_seconds() >= 45:
        raise ValueError('El lector está desconectado. Vuelve a leer la tarjeta.')
    if scan.wallet_id or scan.purpose != 'balance':
        raise ValueError('La lectura ya está vinculada o no es una consulta de tarjeta.')
    if CardScan.objects.filter(reader=scan.reader,created_at__gt=scan.created_at).exists():
        raise ValueError('Hay una lectura más reciente. Comprueba la tarjeta detectada.')
    tag = associate_scan(wallet,item.card_number,pairing_code(scan))
    item.status, item.tag = 'completed', tag
    item.save(update_fields=['status','tag'])
    Audit.objects.create(actor=str(actor),event='card_association_confirmed',reference=str(item.pk),details={'scan':str(scan.pk),'tag':tag.pk})
    return tag
