from urllib.parse import urlsplit
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from core.models import Audit, Tag, Wallet
from core.realtime import emit_event
from .models import TagPortal


def portal_path(portal):
    return reverse('tag-portal', args=[portal.code])


def payload_info(portal):
    """URI shared by NFC and QR. Size includes NDEF record and TLV overhead."""
    base = settings.PUBLIC_URL
    parts = urlsplit(base)
    if parts.scheme not in ('https', 'http') or not parts.netloc or parts.username or parts.password or parts.query or parts.fragment or parts.path not in ('', '/'):
        raise ValidationError('PUBLIC_URL debe ser un origen web sin credenciales ni ruta.')
    if not settings.DEBUG and parts.scheme != 'https':
        raise ValidationError('El enlace de producción requiere HTTPS.')
    uri = base.rstrip('/') + portal_path(portal)
    prefix = 'https://' if parts.scheme == 'https' else 'http://'
    # NFC Forum short URI record: header/type/prefix plus URI suffix; TLV + end.
    payload_size = 1 + len(uri[len(prefix):].encode('utf-8'))
    ndef_size = 4 + payload_size if payload_size <= 255 else 7 + payload_size
    storage_size = ndef_size + (3 if ndef_size < 255 else 5)
    return {'uri': uri, 'ntag213_bytes': storage_size, 'fits_ntag213': storage_size <= 144}


def available(portal):
    return portal.enabled and (not portal.tag_id or portal.tag.active)


def presentation(portal, user):
    """Allowlist shared by SSR and JSON. Never serialize a model to a visitor."""
    if not available(portal):
        return {'state': 'unavailable'}
    owner = bool(user.is_authenticated and user.is_active and portal.tag_id
                 and portal.tag.wallet.user_id == user.pk)
    data = {'state': 'owner' if owner and portal.activated_at else 'new' if not portal.activated_at else 'visitor',
            'title': portal.title, 'message': portal.message, 'theme': portal.theme,
            'can_activate': owner and not portal.activated_at,
            'can_manage': owner, 'path': portal_path(portal)}
    if owner and portal.activated_at:
        data['owner'] = {'display_name': user.first_name or user.username,
                         'activated_at': portal.activated_at.isoformat()}
    return data


@transaction.atomic
def provision_for_owner(tag_id, user):
    # Wallet first, like accounting/association. URL creation never binds a UID.
    wallet = Wallet.objects.select_for_update().get(user=user)
    tag = Tag.objects.select_for_update().get(pk=tag_id, wallet=wallet)
    if not tag.active:
        raise ValidationError('El llavero está bloqueado.')
    portal, created = TagPortal.objects.get_or_create(tag=tag)
    if created:
        Audit.objects.create(actor=str(user.pk), event='tag_portal_created', reference=str(portal.pk))
    return portal


def _locked_owner_portal(code, user):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied
    wallet = Wallet.objects.select_for_update().get(user=user)
    # Resolve only an owned tag; public code/holder parameters confer no rights.
    tag = Tag.objects.select_for_update().get(wallet=wallet, portal__code=code)
    portal = TagPortal.objects.select_for_update().get(code=code, tag=tag)
    portal.tag = tag
    return portal


@transaction.atomic
def activate(code, user):
    portal = _locked_owner_portal(code, user)
    if not available(portal):
        raise PermissionDenied
    if not portal.activated_at:
        portal.activated_at = timezone.now()
        portal.save(update_fields=['activated_at', 'updated_at'])
        Audit.objects.create(actor=str(user.pk), event='tag_portal_activated', reference=str(portal.pk))
        emit_event(portal.tag.wallet_id, 'tag_portal_activated')
    return portal


@transaction.atomic
def block(code, user):
    portal = _locked_owner_portal(code, user)
    if portal.tag.active or portal.enabled:
        Tag.objects.filter(pk=portal.tag_id).update(active=False)
        # Keep old and normalized representations consistent; no ledger writes.
        from backend.apps.credentials.models import NormalizedCredential
        NormalizedCredential.objects.filter(tag_id=portal.tag_id).update(status='disabled')
        portal.enabled = False
        portal.save(update_fields=['enabled', 'updated_at'])
        Audit.objects.create(actor=str(user.pk), event='tag_blocked_by_owner', reference=str(portal.pk))
        emit_event(portal.tag.wallet_id, 'tag_blocked')
    return portal
