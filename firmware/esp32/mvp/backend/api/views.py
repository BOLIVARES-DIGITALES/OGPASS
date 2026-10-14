"""Versioned presentation layer; business rules live in domain services."""
import json
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.db import transaction
from core import views as legacy
from core.cards import scan_data, complete_association
from core.models import Audit, CardAssociationRequest, CardScan
from core.services import balance
from backend.apps.identity.services import identity_for, identity_data
from backend.apps.credentials.services import credentials_for, credential_data, sync_tag
from backend.apps.devices.models import OgpassDevice, HardwareEvent
from backend.apps.devices.services import register_device, record_hardware_event, heartbeat_device, device_data, event_data


def developer(request):
    return request.user.is_staff and settings.OGPASS_MODE == 'developer'


def body(request):
    value = json.loads(request.body)
    if not isinstance(value, dict):
        raise ValueError('Object required')
    return value


@legacy.api_login_required
@require_GET
def me(request):
    return JsonResponse(identity_data(identity_for(request.user)))


@legacy.api_login_required
@require_GET
def wallet(request):
    identity = identity_for(request.user)
    funds = balance(identity.wallet)
    return JsonResponse({'wallet_id': identity.wallet_id, 'currency': 'CLP', 'balance': funds,
                         'available_balance': 0 if identity.wallet.frozen else max(0, funds),
                         'frozen': identity.wallet.frozen, 'source': 'Ledger OGPASS'})


@legacy.api_login_required
@require_GET
def credentials(request):
    return JsonResponse({'credentials': [credential_data(c, developer(request)) for c in credentials_for(request.user)]})


@legacy.api_login_required
@require_GET
def devices(request):
    rows = OgpassDevice.objects.select_related('reader')
    if not request.user.is_staff:
        from django.db.models import Q
        rows = rows.filter(Q(owner=request.user) | Q(normalizedcredential__identity__user=request.user)).distinct()
    return JsonResponse({'devices': [device_data(d, developer(request)) for d in rows[:100]]})


@legacy.api_login_required
@require_POST
@legacy.api_errors
def register(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    payload = body(request)
    device, token = register_device(payload.get('name'), payload.get('driver', 'rc522'), request.user.pk)
    return JsonResponse({'device': device_data(device, developer(request)), 'reader_token': token}, status=201)


@legacy.api_login_required
@require_POST
@legacy.api_errors
def disable(request, device_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    with transaction.atomic():
        device = get_object_or_404(OgpassDevice.objects.select_for_update(), pk=device_id)
        device.reader.active = False
        device.reader.save(update_fields=['active'])
        Audit.objects.create(actor=str(request.user.pk), event='device_disabled', reference=str(device.pk))
    return JsonResponse({'status': 'DISABLED'})


@csrf_exempt
@require_POST
@legacy.api_errors
def scan(request):
    reader = legacy.reader_auth(request)
    if not reader:
        return JsonResponse({'error': 'unauthorized'}, status=401)
    event, created = record_hardware_event(reader, body(request))
    data = event_data(event)
    if event.scan_id:
        data['scan'] = scan_data(event.scan, include_pairing=True)
    return JsonResponse(data, status=201 if created else 200)


@csrf_exempt
@require_POST
@legacy.api_errors
def heartbeat(request):
    reader = legacy.reader_auth(request)
    if not reader:
        return JsonResponse({'error': 'unauthorized'}, status=401)
    return JsonResponse(device_data(heartbeat_device(reader, body(request))))


@legacy.api_login_required
@require_POST
@legacy.api_errors
def assign(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    payload = body(request)
    get_object_or_404(CardAssociationRequest, pk=payload['request_id'])
    get_object_or_404(CardScan, pk=payload['scan_key'])
    tag = complete_association(payload['request_id'], payload['scan_key'], payload['number'], request.user.pk)
    return JsonResponse(credential_data(sync_tag(tag), developer(request)))


@legacy.api_login_required
@require_GET
def recent_events(request):
    rows = HardwareEvent.objects.select_related('device__reader', 'credential')
    if not request.user.is_staff:
        rows = rows.filter(credential__identity__user=request.user)
    return JsonResponse({'events': [event_data(e, developer(request)) for e in rows[:30]]})
