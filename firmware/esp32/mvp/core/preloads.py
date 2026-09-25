"""No minting: a preload reserves existing CLP before its recipient can activate it."""
import uuid
from django.db import transaction
from django.utils import timezone
from .models import Wallet, Preload
from .services import balance, post, Conflict
from .realtime import emit_event


@transaction.atomic
def issue_preload(issuer, recipient, amount, key):
    if type(amount) is not int or not 1 <= amount <= 200000:
        raise ValueError('La prerecarga debe ser de $1 a $200.000 CLP.')
    issuer = Wallet.objects.select_for_update().select_related('user').get(pk=issuer.pk)
    if not issuer.user.is_staff or not issuer.user.is_active:
        raise ValueError('Solo un administrador activo puede asignar prerecargas.')
    existing = Preload.objects.filter(key=key).first()
    if existing:
        if (existing.issuer_id,existing.recipient_id,existing.amount) != (issuer.pk,recipient.pk,amount):
            raise Conflict('La referencia ya se utilizó con otros datos.')
        return existing
    if issuer.frozen or balance(issuer) < amount:
        raise ValueError('Fondos OGPASS insuficientes o bloqueados. Primero confirma una recarga real en la cuenta administradora.')
    if not recipient.user.is_active:
        raise ValueError('La cuenta de destino está desactivada.')
    preload_id = uuid.uuid4()
    journal = post(f'preload:reserve:{preload_id}','preload_reserve',str(issuer.user_id),[(f'wallet:{issuer.pk}',amount),(f'preload:{preload_id}',-amount)])
    preload = Preload.objects.create(id=preload_id,key=key,issuer=issuer,recipient=recipient,amount=amount,reserve_journal=journal)
    emit_event(issuer.pk,'preload_reserved')
    emit_event(recipient.pk,'preload_assigned')
    return preload


@transaction.atomic
def activate_preload(wallet, preload_id):
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    preload = Preload.objects.select_for_update().get(pk=preload_id,recipient=wallet)
    if preload.status == 'activated': return preload
    if preload.status != 'ready': raise Conflict('Esta prerecarga ya no está disponible.')
    if wallet.frozen or Wallet.objects.filter(pk=preload.issuer_id,frozen=True).exists():
        raise ValueError('La cuenta receptora o la fuente de fondos está en revisión.')
    preload.settlement_journal = post(f'preload:activate:{preload.pk}','preload_activate',str(wallet.user_id),[(f'preload:{preload.pk}',preload.amount),(f'wallet:{wallet.pk}',-preload.amount)])
    preload.status,preload.activated_at = 'activated',timezone.now()
    preload.save(update_fields=['status','activated_at','settlement_journal'])
    emit_event(wallet.pk,'preload_activated')
    emit_event(preload.issuer_id,'preload_activated')
    return preload


@transaction.atomic
def cancel_preload(issuer, preload_id):
    issuer = Wallet.objects.select_for_update().get(pk=issuer.pk)
    preload = Preload.objects.select_for_update().get(pk=preload_id,issuer=issuer)
    if preload.status == 'cancelled': return preload
    if preload.status != 'ready': raise Conflict('Una prerecarga activada no puede cancelarse.')
    preload.settlement_journal = post(f'preload:cancel:{preload.pk}','preload_cancel',str(issuer.user_id),[(f'preload:{preload.pk}',preload.amount),(f'wallet:{issuer.pk}',-preload.amount)])
    preload.status = 'cancelled'
    preload.save(update_fields=['status','settlement_journal'])
    emit_event(issuer.pk,'preload_cancelled')
    emit_event(preload.recipient_id,'preload_cancelled')
    return preload
