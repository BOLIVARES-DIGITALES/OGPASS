import hashlib
import json
import secrets
import uuid
from django.db import connection, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from core.cards import record_scan
from core.models import Reader, Tag, Audit
from core.services import Conflict
from backend.apps.credentials.models import NormalizedCredential
from backend.apps.credentials.normalizer import normalize, DRIVERS
from backend.apps.credentials.services import sync_tag
from .models import OgpassDevice, HardwareEvent


def device_for(reader):
    return OgpassDevice.objects.get_or_create(reader=reader, defaults={'capabilities': DRIVERS['rc522']})[0]


@transaction.atomic
def register_device(name, driver, actor):
    if not isinstance(name, str) or not name.strip() or len(name) > 64 or driver not in DRIVERS:
        raise ValueError('Invalid device')
    if Reader.objects.filter(name=name.strip()).exists():
        raise Conflict('El nombre ya está registrado; no se rota su token automáticamente')
    token = secrets.token_urlsafe(32)
    reader = Reader.objects.create(name=name.strip(), token_hash=hashlib.sha256(token.encode()).hexdigest(), amount=1000, cost=700)
    device = OgpassDevice.objects.create(reader=reader, driver=driver, capabilities=DRIVERS[driver])
    Audit.objects.create(actor=str(actor), event='device_registered', reference=str(device.pk))
    return device, token


@transaction.atomic
def record_hardware_event(reader, payload):
    normalized = normalize(payload)
    if payload.get('purpose', 'balance') != 'balance':
        raise ValueError('Hardware events are read-only; use the existing explicit payment flow')
    event_id = uuid.UUID(str(payload['event_id']))
    request_id = uuid.UUID(str(payload.get('request_id', event_id)))
    timestamp = payload.get('timestamp')
    observed = parse_datetime(timestamp) if isinstance(timestamp, str) else None
    if timestamp is not None and (not observed or timezone.is_naive(observed)):
        raise ValueError('Timestamp must include timezone')
    fingerprint = hashlib.sha256(json.dumps({'credential': normalized, 'timestamp': timestamp}, sort_keys=True).encode()).hexdigest()
    device = device_for(reader)
    device = OgpassDevice.objects.select_for_update().get(pk=device.pk)
    if not Reader.objects.filter(pk=reader.pk, active=True).exists():
        raise ValueError('Disabled reader')
    if device.driver != normalized['source']:
        raise ValueError('Driver does not match registered device')
    if payload.get('device_id') and str(payload['device_id']) != str(device.pk):
        raise ValueError('Device identity is assigned by server')
    existing = HardwareEvent.objects.filter(pk=event_id).first()
    if existing:
        if existing.device_id != device.pk or existing.fingerprint != fingerprint:
            raise Conflict('El evento ya corresponde a otra lectura')
        return existing, False
    scan = credential = None
    if normalized['recognized']:
        scan = record_scan(reader, normalized['uid'], event_id)
        defaults = {key: normalized[key] for key in ('technology', 'protocol', 'uid', 'source', 'metadata', 'capabilities')}
        credential, _ = NormalizedCredential.objects.get_or_create(identifier_hash=normalized['identifier_hash'], defaults=defaults)
        credential.device, credential.last_seen = device, timezone.now()
        credential.metadata = normalized['metadata']
        credential.source, credential.capabilities = normalized['source'], normalized['capabilities']
        credential.save(update_fields=['device', 'last_seen', 'metadata', 'source', 'capabilities'])
        tag = Tag.objects.filter(uid=normalized['uid']).select_related('wallet__user').first()
        if tag:
            credential = sync_tag(tag)
    event = HardwareEvent.objects.create(event_id=event_id, request_id=request_id,
        device=device, credential=credential, scan=scan, fingerprint=fingerprint,
        status='detected' if normalized['recognized'] else 'UNKNOWN_TECHNOLOGY',
        metadata=normalized['metadata'], observed_at=observed)
    Reader.objects.filter(pk=reader.pk).update(last_seen=timezone.now())
    Audit.objects.create(actor=f'reader:{reader.pk}', event='hardware_event', reference=str(event_id))
    # Existing staff SSE uses channel 0. PostgreSQL delivers this only at commit.
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_notify(%s, %s)', ['ogpass_wallet_events', '0'])
    return event, True


@transaction.atomic
def heartbeat_device(reader, payload):
    if not isinstance(payload, dict):
        raise ValueError('Invalid heartbeat')
    firmware = payload.get('firmware_version', '')
    health = payload.get('health', {})
    if not isinstance(firmware, str) or len(firmware) > 40 or not isinstance(health, dict):
        raise ValueError('Invalid health')
    if set(health) - set(DRIVERS) or any(state not in ('CONNECTED', 'OFFLINE', 'ERROR', 'DISABLED') for state in health.values()):
        raise ValueError('Invalid driver state')
    device = device_for(reader)
    device.firmware_version, device.health = firmware, health
    device.save(update_fields=['firmware_version', 'health'])
    Reader.objects.filter(pk=reader.pk, active=True).update(last_seen=timezone.now())
    return device


def device_data(device, developer=False):
    reader = device.reader
    online = bool(reader.active and reader.last_seen and (timezone.now() - reader.last_seen).total_seconds() < 45)
    result = {'device_id': str(device.pk), 'name': reader.name, 'device_type': device.device_type,
              'status': 'ONLINE' if online else 'OFFLINE' if reader.active else 'DISABLED',
              'last_seen': reader.last_seen.isoformat() if reader.last_seen else None}
    if developer:
        result.update(driver=device.driver, reader_type=device.driver,
                      firmware_version=device.firmware_version, capabilities=device.capabilities,
                      health=device.health, role='PRIMARY' if device.driver == 'rc522' else 'OPTIONAL')
    return result


def event_data(event, developer=False):
    result = {'event_id': str(event.pk), 'request_id': str(event.request_id),
              'device_id': str(event.device_id), 'device_name': event.device.reader.name,
              'credential_id': str(event.credential_id) if event.credential_id else None,
              'status': event.status, 'timestamp': event.created_at.isoformat(),
              'technology': event.credential.technology if event.credential_id else 'UNKNOWN_TECHNOLOGY'}
    if developer:
        result['metadata'] = event.metadata
        if event.credential_id:
            result.update(uid=event.credential.uid, protocol=event.credential.protocol,
                          driver=event.credential.source, capabilities=event.credential.capabilities)
    return result

