import base64
import hashlib
import hmac
import re
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from nacl.exceptions import CryptoError
from nacl.secret import SecretBox

from .models import (
    Audit,
    ExternalTransitBalanceSnapshot,
    ExternalTransitCredential,
    StellarAccount,
    Tag,
    Wallet,
)
from .adapters import Stellar
from .services import balance as ogpass_balance


class CredentialError(ValueError):
    pass


class CredentialConflict(CredentialError):
    pass


def normalize_reference(issuer, value):
    issuer = str(issuer or '').strip().upper()
    if issuer not in ExternalTransitCredential.Issuer.values:
        raise CredentialError('Emisor no compatible.')
    reference = re.sub(r'[\s.-]', '', str(value or '').strip()).upper()
    if issuer == ExternalTransitCredential.Issuer.OG:
        if not re.fullmatch(r'[A-Z0-9]{4,24}', reference):
            raise CredentialError('Ingresa un número OGPASS válido.')
    elif not re.fullmatch(r'\d{6,24}', reference):
        raise CredentialError('Ingresa sólo los dígitos impresos en la tarjeta.')
    return issuer, reference


def _key(value, label):
    if not value:
        raise CredentialError(f'Falta configurar {label}.')
    return hashlib.sha256(value.encode('utf-8')).digest()


def encrypt_reference(reference):
    box = SecretBox(_key(settings.CREDENTIAL_ENCRYPTION_KEY, 'CREDENTIAL_ENCRYPTION_KEY'))
    return base64.urlsafe_b64encode(bytes(box.encrypt(reference.encode('utf-8')))).decode('ascii')


def decrypt_reference(ciphertext):
    box = SecretBox(_key(settings.CREDENTIAL_ENCRYPTION_KEY, 'CREDENTIAL_ENCRYPTION_KEY'))
    try:
        return box.decrypt(base64.urlsafe_b64decode(ciphertext.encode('ascii'))).decode('utf-8')
    except (ValueError, CryptoError) as exc:
        raise CredentialError('No fue posible leer la referencia protegida.') from exc


def reference_hmac(issuer, reference):
    key = _key(settings.CREDENTIAL_HMAC_KEY, 'CREDENTIAL_HMAC_KEY')
    return hmac.new(key, f'{issuer}:{reference}'.encode('utf-8'), hashlib.sha256).hexdigest()


def mask_reference(reference):
    visible = 4 if len(reference) > 6 else 2
    return f'{"•" * max(0, len(reference) - visible)}{reference[-visible:]}'


@transaction.atomic
def declare_credential(user, issuer, reference, consent_version):
    issuer, reference = normalize_reference(issuer, reference)
    consent_version = str(consent_version or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9._-]{3,48}', consent_version):
        raise CredentialError('Versión de consentimiento inválida.')
    digest = reference_hmac(issuer, reference)
    existing = ExternalTransitCredential.objects.select_for_update().filter(issuer=issuer, reference_hmac=digest).first()
    if existing and existing.user_id != user.pk:
        raise CredentialConflict('Esta credencial ya está asociada a otra cuenta.')
    created = existing is None
    credential = existing or ExternalTransitCredential(user=user, issuer=issuer, reference_hmac=digest)
    credential.encrypted_reference = encrypt_reference(reference)
    credential.consent_version = consent_version
    credential.consented_at = timezone.now()
    if credential.verification_status == ExternalTransitCredential.VerificationStatus.REVOKED:
        credential.verification_status = ExternalTransitCredential.VerificationStatus.DECLARED
    credential.save()
    Audit.objects.create(
        actor=str(user.pk),
        event='external_transit_credential_declared',
        reference=str(credential.pk),
        details={'issuer': issuer, 'consent_version': consent_version, 'created': created},
    )
    return credential, created


def credential_data(credential):
    reference = decrypt_reference(credential.encrypted_reference)
    return {
        'id': str(credential.pk),
        'issuer': credential.issuer,
        'reference_masked': mask_reference(reference),
        'verification_status': credential.verification_status,
        'consent_version': credential.consent_version,
        'consented_at': credential.consented_at.isoformat(),
    }


@transaction.atomic
def revoke_credential(credential, actor):
    credential = ExternalTransitCredential.objects.select_for_update().get(pk=credential.pk)
    if credential.verification_status != ExternalTransitCredential.VerificationStatus.REVOKED:
        credential.verification_status = ExternalTransitCredential.VerificationStatus.REVOKED
        credential.save(update_fields=['verification_status', 'updated_at'])
        Audit.objects.create(
            actor=str(actor),
            event='external_transit_credential_revoked',
            reference=str(credential.pk),
            details={'issuer': credential.issuer},
        )
    return credential


def _movired_balance(reference):
    endpoint = settings.MOVIRED_BALANCE_API_URL
    token = settings.MOVIRED_BALANCE_API_TOKEN
    if not endpoint or not token:
        return {
            'status': 'integration_required',
            'balance': None,
            'currency': 'CLP',
            'source': 'Movired · consulta oficial',
            'source_url': 'https://new.movired.cl/',
            'observed_at': None,
            'message': 'La consulta automática requiere una API de saldo habilitada por Movired.',
            'products': ['Consulta de saldo Red Movilidad'],
        }
    parsed = urlparse(endpoint)
    if parsed.scheme != 'https' or parsed.hostname not in settings.MOVIRED_ALLOWED_HOSTS:
        raise CredentialError('La URL autorizada de Movired no cumple la política de seguridad.')
    try:
        response = requests.post(
            endpoint,
            json={'number': reference},
            headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
            timeout=(3, 8),
        )
        response.raise_for_status()
        payload = response.json()
        amount = payload.get('balance_clp')
        if payload.get('status') != 'verified' or isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise CredentialError('Movired respondió sin un saldo verificable.')
        observed_at = parse_datetime(str(payload.get('observed_at') or ''))
        if observed_at is None:
            observed_at = timezone.now()
        return {
            'status': 'verified',
            'balance': amount,
            'currency': 'CLP',
            'source': 'Movired · API autorizada',
            'source_url': 'https://new.movired.cl/',
            'observed_at': observed_at,
            'message': 'Saldo consultado en la integración autorizada de Movired.',
            'products': ['Consulta de saldo Red Movilidad'],
        }
    except (requests.RequestException, ValueError, CredentialError) as exc:
        return {
            'status': 'unavailable',
            'balance': None,
            'currency': 'CLP',
            'source': 'Movired · API autorizada',
            'source_url': 'https://new.movired.cl/',
            'observed_at': None,
            'message': 'Movired no respondió con un saldo verificable. Intenta nuevamente.',
            'products': ['Consulta de saldo Red Movilidad'],
        }


def _metro_product(user):
    credential = (
        ExternalTransitCredential.objects.filter(
            user=user,
            issuer=ExternalTransitCredential.Issuer.RED,
        )
        .exclude(verification_status=ExternalTransitCredential.VerificationStatus.REVOKED)
        .order_by('-updated_at')
        .first()
    )
    snapshot = (
        credential.balance_snapshots.order_by('-queried_at').first()
        if credential
        else None
    )
    verified = bool(snapshot and snapshot.status == 'verified' and snapshot.balance_amount is not None)
    if verified:
        message = 'Último saldo verificado por la integración autorizada de Red Movilidad.'
        status = 'verified'
    elif credential:
        message = 'La tarjeta RED está declarada, pero la integración todavía no entrega saldos, deuda, facturación ni movimientos.'
        status = snapshot.status if snapshot else 'integration_required'
    else:
        message = 'Vincula una tarjeta RED para habilitar la consulta cuando exista una integración autorizada.'
        status = 'not_linked'
    return {
        'integration_status': status,
        'available_balance': snapshot.balance_amount if verified else None,
        'outstanding_balance': None,
        'billed_balance': None,
        'currency': 'CLP',
        'updated_at': snapshot.observed_at.isoformat() if snapshot and snapshot.observed_at else None,
        'recent_movements': [],
        'message': message,
    }


def _native_xlm(stellar_result):
    for balance in stellar_result.get('balances', []):
        if balance.get('asset_type') == 'native':
            value = balance.get('balance')
            return str(value) if value is not None else None
    return None


def _web3_product(wallet):
    accounts = []
    for account in StellarAccount.objects.filter(wallet=wallet).order_by('network'):
        result = Stellar().balance(account)
        accounts.append({
            'network': account.network,
            'address': account.address,
            'status': result['status'],
            'available_xlm': _native_xlm(result) if result['status'] == 'connected' else None,
            'updated_at': result.get('updated_at'),
            'source_url': result.get('source_url'),
        })
    if not accounts:
        status = 'not_linked'
        message = 'Vincula una dirección pública Stellar para consultar XLM on-chain.'
    elif any(account['status'] == 'connected' for account in accounts):
        status = 'connected'
        message = 'Saldo XLM leído directamente desde Stellar. Testnet y mainnet se muestran por separado.'
    else:
        status = 'unavailable'
        message = 'La dirección está vinculada, pero Stellar no entregó un saldo verificable.'
    return {
        'integration_status': status,
        'accounts': accounts,
        'credit_line_xlm': None,
        'debt_xlm': None,
        'message': message,
    }


def query_balance(credential):
    credential = ExternalTransitCredential.objects.get(pk=credential.pk)
    if credential.verification_status == ExternalTransitCredential.VerificationStatus.REVOKED:
        result = {
            'status': 'revoked', 'balance': None, 'currency': 'CLP',
            'source': 'OGPASS', 'source_url': None, 'observed_at': None,
            'message': 'La credencial fue revocada.', 'products': [],
        }
    else:
        reference = decrypt_reference(credential.encrypted_reference)
        if credential.issuer == ExternalTransitCredential.Issuer.OG:
            wallet = Wallet.objects.get(user=credential.user)
            tag = Tag.objects.filter(wallet=wallet, card_number=reference, active=True).first()
            if tag:
                result = {
                    'status': 'verified', 'balance': ogpass_balance(wallet), 'currency': 'CLP',
                    'source': 'Ledger OGPASS', 'source_url': None, 'observed_at': timezone.now(),
                    'message': 'Saldo disponible de tu cuenta OGPASS.',
                    'products': ['Billetera OGPASS', 'Consulta NFC'],
                    'product_details': {
                        'red_metro': _metro_product(credential.user),
                        'red_web3': _web3_product(wallet),
                    },
                }
            else:
                result = {
                    'status': 'verification_required', 'balance': None, 'currency': 'CLP',
                    'source': 'Ledger OGPASS', 'source_url': None, 'observed_at': None,
                    'message': 'Asocia físicamente esta tarjeta a tu cuenta OGPASS para verificarla.',
                    'products': [],
                }
        elif credential.issuer == ExternalTransitCredential.Issuer.RED:
            result = _movired_balance(reference)
        else:
            result = {
                'status': 'integration_required', 'balance': None, 'currency': 'ARS',
                'source': 'SUBE', 'source_url': 'https://www.argentina.gob.ar/sube', 'observed_at': None,
                'message': 'La integración oficial con SUBE todavía no está habilitada.',
                'products': ['Credencial SUBE declarada'],
            }
    observed_at = result.get('observed_at')
    with transaction.atomic():
        credential = ExternalTransitCredential.objects.select_for_update().get(pk=credential.pk)
        ExternalTransitBalanceSnapshot.objects.create(
            credential=credential,
            status=result['status'],
            balance_amount=result.get('balance'),
            currency=result['currency'],
            source=result['source'],
            observed_at=observed_at,
        )
        if result['status'] == 'verified' and credential.verification_status != ExternalTransitCredential.VerificationStatus.VERIFIED:
            credential.verification_status = ExternalTransitCredential.VerificationStatus.VERIFIED
            credential.save(update_fields=['verification_status', 'updated_at'])
    result['observed_at'] = observed_at.isoformat() if observed_at else None
    result['credential'] = credential_data(credential)
    return result
