from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from core.models import Tag, Wallet
from .models import TagPortal
from . import services


def _portal(code):
    return get_object_or_404(TagPortal.objects.select_related('tag__wallet'), code=code)


@require_GET
def landing(request, code):
    portal = _portal(code)
    data = services.presentation(portal, request.user)
    return render(request, 'tag_portal/landing.html', {
        'portal': data, 'login_url': '/login/?' + urlencode({'next': services.portal_path(portal)})
    }, status=404 if data['state'] == 'unavailable' else 200)


@require_GET
def public_state(request, code):
    portal = _portal(code)
    data = services.presentation(portal, request.user)
    return JsonResponse(data, status=404 if data['state'] == 'unavailable' else 200)


@login_required
@require_POST
def activate(request, code):
    try:
        portal = services.activate(code, request.user)
    except (Tag.DoesNotExist, Wallet.DoesNotExist, TagPortal.DoesNotExist):
        raise PermissionDenied
    messages.success(request, 'Acceso activado. Tu saldo y tus medios de pago no han cambiado.')
    return redirect(services.portal_path(portal))


@login_required
@require_POST
def block(request, code):
    if request.POST.get('confirm') != 'block':
        return JsonResponse({'error': 'Confirma el bloqueo del llavero.'}, status=400)
    try:
        services.block(code, request.user)
    except (Tag.DoesNotExist, Wallet.DoesNotExist, TagPortal.DoesNotExist):
        raise PermissionDenied
    messages.success(request, 'Llavero bloqueado. Tus fondos permanecen en tu cuenta.')
    return redirect('my-tag-portals')


@login_required
@require_GET
def my_tags(request):
    rows = []
    for tag in Tag.objects.filter(wallet__user=request.user).select_related('portal').order_by('pk'):
        portal = getattr(tag, 'portal', None)
        payload = None
        if portal and services.available(portal):
            try:
                payload = services.payload_info(portal)
            except ValidationError:
                messages.error(request, 'La URL pública necesita configuración del administrador.')
        rows.append({'tag_id': tag.pk, 'label': f'Llavero {tag.pk}', 'active': tag.active,
                     'portal': portal, 'payload': payload})
    return render(request, 'tag_portal/my_tags.html', {'tag_rows': rows})


@login_required
@require_POST
def provision(request, tag_id):
    try:
        services.provision_for_owner(tag_id, request.user)
    except (Tag.DoesNotExist, Wallet.DoesNotExist):
        raise PermissionDenied
    except ValidationError:
        messages.error(request, 'No se puede crear un enlace para un llavero bloqueado.')
    return redirect('my-tag-portals')
