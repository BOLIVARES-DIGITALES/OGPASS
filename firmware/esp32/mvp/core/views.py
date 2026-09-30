import json, uuid, hashlib, secrets
from functools import wraps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST, require_GET
from .models import Wallet, Reader, Tag, Operation, TopUp, Audit, StellarAccount, CardScan, Preload, CardAssociationRequest, ExternalTransitCredential
from .services import balance, bind_tag, touch, decide, reverse_operation, apply_payment, reconciliation, Conflict, expire_operations
from .adapters import MercadoPago, Stellar, Transport, IntegrationError
from .cards import associate_scan, record_scan, scan_data, card_number_normalize
from .preloads import issue_preload, activate_preload, cancel_preload
from .transit_credentials import CredentialConflict, CredentialError, credential_data, declare_credential, query_balance, revoke_credential


def stellar_public_address(value):
    """Validate a public Stellar account; secrets are never accepted by this API."""
    from stellar_sdk import Keypair
    address = str(value or '').strip()
    try:
        Keypair.from_public_key(address)
    except Exception as exc:
        raise ValueError('Ingresa una dirección pública Stellar válida (G...).') from exc
    return address

def api_errors(fn):
    @wraps(fn)
    def wrapped(*a,**kw):
        try: return fn(*a,**kw)
        except Conflict as e: return JsonResponse({'error':str(e)},status=409)
        except (ValueError,KeyError,TypeError,ValidationError) as e: return JsonResponse({'error':'Solicitud inválida'},status=400)
        except IntegrityError: return JsonResponse({'error':'Conflicto: reintente con la misma referencia'},status=409)
        except IntegrationError as e: return JsonResponse({'error':str(e)},status=503)
    return wrapped

def api_login_required(fn):
    @wraps(fn)
    def wrapped(request,*a,**kw):
        if not request.user.is_authenticated:
            return JsonResponse({'error':'authentication_required'},status=401)
        return fn(request,*a,**kw)
    return wrapped

def wallet_for(user): return Wallet.objects.get_or_create(user=user)[0]

@ensure_csrf_cookie
@require_GET
def session_state(request):
    return JsonResponse({'authenticated':request.user.is_authenticated,'user':request.user.username if request.user.is_authenticated else None})

@api_login_required
@require_POST
def transit_credentials(request):
    try:
        payload=json.loads(request.body)
        if payload.get('consent') is not True:
            raise CredentialError('Debes aceptar el uso indicado de la credencial.')
        credential,created=declare_credential(request.user,payload.get('issuer'),payload.get('reference'),payload.get('consent_version'))
        response=JsonResponse({'credential':credential_data(credential),'created':created},status=201 if created else 200)
    except CredentialConflict as exc:
        response=JsonResponse({'error':str(exc)},status=409)
    except (CredentialError,ValueError,TypeError) as exc:
        response=JsonResponse({'error':str(exc) or 'Solicitud inválida'},status=400)
    except IntegrityError:
        response=JsonResponse({'error':'La credencial ya está asociada.'},status=409)
    response['Cache-Control']='no-store, private'
    return response

@api_login_required
@require_POST
def transit_credential_balance(request,credential_id):
    credential=get_object_or_404(ExternalTransitCredential,pk=credential_id,user=request.user)
    try:
        response=JsonResponse(query_balance(credential))
    except CredentialError as exc:
        response=JsonResponse({'error':str(exc)},status=503)
    response['Cache-Control']='no-store, private'
    return response

@api_login_required
@require_POST
def revoke_transit_credential(request,credential_id):
    credential=get_object_or_404(ExternalTransitCredential,pk=credential_id,user=request.user)
    response=JsonResponse({'credential':credential_data(revoke_credential(credential,request.user.pk))})
    response['Cache-Control']='no-store, private'
    return response

def reader_auth(request):
    token = request.headers.get('Authorization','').removeprefix('Bearer ')
    if not token: return None
    return Reader.objects.filter(token_hash=hashlib.sha256(token.encode()).hexdigest(),active=True).first()

def op_data(op):
    status = 'expired' if op.status == 'pending' and op.expires_at < timezone.now() else op.status
    return {'id':str(op.pk),'status':status,'amount':op.amount,'cost':op.cost,'margin':op.margin,'reason':op.reason,'created_at':op.created_at.isoformat(),'expires_at':op.expires_at.isoformat(),'reader':op.reader.name}

def register(request):
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
            Wallet.objects.create(user=user)
            Audit.objects.create(actor=str(user.pk),event='account_created',reference=str(user.pk))
        login(request,user)
        return redirect('/')
    return render(request,'registration/register.html',{'form':form})

@login_required
def home(request):
    wallet = wallet_for(request.user)
    try: card_number = card_number_normalize(request.GET.get('card_number',''))
    except ValueError: card_number = ''
    return render(request,'home.html',{'card_number':card_number,'wallet':wallet,'balance':balance(wallet),'association_request':CardAssociationRequest.objects.filter(wallet=wallet,status='pending').first(),'tags':Tag.objects.filter(wallet=wallet),'payments_enabled':settings.PAYMENTS_ENABLED,'topup_key':uuid.uuid4()})

@login_required
@require_GET
def state(request):
    expire_operations()
    wallet = wallet_for(request.user)
    now = timezone.now()
    pending = Operation.objects.filter(wallet=wallet,status='pending',expires_at__gte=now).select_related('reader').order_by('-created_at')
    operations = Operation.objects.filter(wallet=wallet).select_related('reader').order_by('-created_at')[:20]
    topups = TopUp.objects.filter(wallet=wallet).order_by('-created_at')[:10]
    recent_scan = CardScan.objects.filter(wallet=wallet).select_related('reader','operation').order_by('-created_at').first()
    preload_rows = list(Preload.objects.filter(recipient=wallet,status='ready').order_by('-created_at')) + list(Preload.objects.filter(recipient=wallet).exclude(status='ready').order_by('-created_at')[:20])
    preloads = [{'id':str(p.pk),'amount':p.amount,'status':p.status,'created_at':p.created_at.isoformat(),'activated_at':p.activated_at.isoformat() if p.activated_at else None} for p in preload_rows]
    readers = [{'name':r.name,'online':bool(r.last_seen and (now-r.last_seen).total_seconds()<45)} for r in Reader.objects.filter(active=True)]
    return JsonResponse({'cards':[{'number':t.card_number,'active':t.active} for t in Tag.objects.filter(wallet=wallet)],'association_pending':list(CardAssociationRequest.objects.filter(wallet=wallet,status='pending').values_list('card_number',flat=True)),'preloads':preloads,'readers':readers,'last_scan':scan_data(recent_scan) if recent_scan else None,'balance':balance(wallet),'source':'Ledger OGPASS · CLP','updated_at':now.isoformat(),'frozen':wallet.frozen,'pending':[op_data(o) for o in pending],'operations':[op_data(o) for o in operations],'topups':[{'id':str(t.pk),'amount':t.amount,'status':t.status,'created_at':t.created_at.isoformat()} for t in topups]})

@login_required
@require_GET
def external_state(request):
    wallet = wallet_for(request.user)
    return JsonResponse({'stellar':[Stellar().balance(a) for a in StellarAccount.objects.filter(wallet=wallet)],'transport':Transport().balance(wallet)})


@login_required
@require_POST
@api_errors
def link_stellar_account(request):
    """Link one self-custodied public account per network to the caller's wallet."""
    payload = json.loads(request.body)
    network = payload.get('network')
    if network not in ('testnet', 'mainnet'):
        raise ValueError('Selecciona Testnet o Mainnet.')
    address = stellar_public_address(payload.get('address'))
    wallet = wallet_for(request.user)
    created = False
    with transaction.atomic():
        account = StellarAccount.objects.select_for_update().filter(wallet=wallet, network=network).first()
        if account and account.address != address:
            raise Conflict('Ya tienes una dirección vinculada para esta red. No se reemplaza automáticamente.')
        if account is None:
            account = StellarAccount.objects.create(wallet=wallet, network=network, address=address)
            created = True
            Audit.objects.create(
                actor=str(request.user.pk),
                event='stellar_account_linked',
                reference=address,
                details={'network': network, 'mode': 'public_read_only'},
            )
    result = Stellar().balance(account)
    result['created'] = created
    response = JsonResponse(result, status=201 if created else 200)
    response['Cache-Control'] = 'no-store, private'
    return response

@login_required
@require_POST
def associate(request):
    from urllib.parse import urlencode
    number = request.POST.get('card_number','')
    if 'pairing_code' not in request.POST:
        from .cards import request_association
        try:
            request_association(wallet_for(request.user),number)
            messages.success(request,'Número de tarjeta guardado. Revisa en Mi tarjeta las fuentes de saldo disponibles.')
        except ValueError as e: messages.error(request,str(e))
        return redirect('/#my-card')
    try:
        if request.POST.get('consent') != 'yes':
            raise ValueError('Confirma que quieres usar esta tarjeta para consultar tus fondos OGPASS.')
        tag = associate_scan(wallet_for(request.user),number,request.POST.get('pairing_code',''),request.POST.get('replace_tag') or None)
    except (ValueError,IntegrityError) as e:
        messages.error(request,str(e) if isinstance(e,ValueError) else 'La tarjeta ya está asociada. Vuelve a escanearla.')
        try: number = card_number_normalize(number)
        except ValueError: number = ''
        return redirect('/?'+urlencode({'card_number':number})+'#my-card')
    messages.success(request,f'Tarjeta {tag.card_number} asociada. Escanéala para consultar tu saldo OGPASS sin realizar un cobro.')
    return redirect('/#my-card')

@login_required
@require_POST
@api_errors
def confirm(request, op_id):
    get_object_or_404(Operation,pk=op_id,wallet=wallet_for(request.user))
    return JsonResponse(op_data(decide(wallet_for(request.user),op_id,json.loads(request.body).get('approve') is True)))

@login_required
@require_POST
def topup(request):
    if not settings.PAYMENTS_ENABLED:
        messages.error(request,'Recargas deshabilitadas: medio de pago pendiente de conexión.')
        return redirect('/')
    try:
        amount = int(request.POST['amount'])
        key = uuid.UUID(request.POST['key'])
        if not 500 <= amount <= 200000: raise ValueError('Monto entre $500 y $200.000 CLP')
        wallet = wallet_for(request.user)
        with transaction.atomic():
            Wallet.objects.select_for_update().get(pk=wallet.pk)
            t, _ = TopUp.objects.get_or_create(key=key,defaults={'wallet':wallet,'amount':amount})
            if t.wallet_id != wallet.pk or t.amount != amount: raise Conflict('Referencia ya usada')
            if not t.checkout_url:
                t.preference_id,t.checkout_url = MercadoPago().checkout(t)
                t.save(update_fields=['preference_id','checkout_url'])
        return redirect(t.checkout_url)
    except (ValueError,KeyError,IntegrationError,IntegrityError) as e:
        messages.error(request,str(e) if not isinstance(e,IntegrityError) else 'Referencia ocupada; vuelva a intentar')
        return redirect('/')

@csrf_exempt
@require_POST
@api_errors
def webhook(request):
    adapter = MercadoPago()
    if not adapter.verify(request): return JsonResponse({'error':'invalid_signature'},status=401)
    payload = json.loads(request.body)
    if payload.get('type') != 'payment': return JsonResponse({'status':'ignored'})
    payment_id = request.GET['data.id']
    if str(payload.get('data',{}).get('id')) != payment_id: raise ValueError('Mismatched payment ID')
    payment = adapter.payment(payment_id)
    try: t = apply_payment(payment)
    except TopUp.DoesNotExist:
        Audit.objects.create(actor='mercadopago',event='unmatched_payment',reference=payment_id)
        return JsonResponse({'error':'unknown_reference'},status=409)
    return JsonResponse({'status':t.status})

@csrf_exempt
@require_POST
@api_errors
def reader_touch(request):
    reader = reader_auth(request)
    if not reader: return JsonResponse({'error':'unauthorized'},status=401)
    data = json.loads(request.body)
    return JsonResponse(op_data(touch(reader,data['uid'],uuid.UUID(data['key']))))

@csrf_exempt
@require_POST
def heartbeat(request):
    reader = reader_auth(request)
    if not reader: return JsonResponse({'error':'unauthorized'},status=401)
    Reader.objects.filter(pk=reader.pk).update(last_seen=timezone.now())
    return JsonResponse({'status':'online','amount':reader.amount})

@require_GET
def reader_operation(request, key):
    reader = reader_auth(request)
    if not reader: return JsonResponse({'error':'unauthorized'},status=401)
    op = get_object_or_404(Operation,key=key,reader=reader)
    Reader.objects.filter(pk=reader.pk).update(last_seen=timezone.now())
    return JsonResponse(op_data(op))

@staff_member_required
def dashboard(request):
    expire_operations()
    now = timezone.now()
    readers = list(Reader.objects.all())
    for r in readers: r.online = bool(r.last_seen and (now-r.last_seen).total_seconds()<45)
    return render(request,'dashboard.html',{'preload_key':uuid.uuid4(),'funding_balance':balance(wallet_for(request.user)),'preloads':Preload.objects.select_related('recipient__user','issuer__user').order_by('-created_at')[:100],'report':reconciliation(),'readers':readers,'operations':Operation.objects.select_related('reader','wallet__user').order_by('-created_at')[:100],'topups':TopUp.objects.select_related('wallet__user').order_by('-created_at')[:100],'audits':Audit.objects.order_by('-created_at')[:30],'frozen':Wallet.objects.filter(frozen=True).count(),'payments_enabled':settings.PAYMENTS_ENABLED,'updated_at':now})

@staff_member_required
@require_POST
def reverse(request, op_id):
    try: reverse_operation(op_id,str(request.user.pk),request.POST.get('reason',''))
    except (ValueError,Operation.DoesNotExist) as e: messages.error(request,str(e))
    else: messages.success(request,'Reverso registrado. Costo revertido: confirma que el servicio no fue prestado.')
    return redirect('/ops/')

@staff_member_required
@require_POST
def reconcile_payment(request):
    try:
        t = apply_payment(MercadoPago().payment(request.POST.get('payment_id','')))
        messages.success(request,'Pago consultado: '+t.status)
    except (ValueError,IntegrationError,TopUp.DoesNotExist,IntegrityError): messages.error(request,'No se pudo conciliar; verifique ID, importe, moneda y referencia.')
    return redirect('/ops/')

@require_GET
def health(request):
    from django.db import connection
    with connection.cursor() as cur: cur.execute('SELECT 1')
    return JsonResponse({'status':'ok','service':'ogpass','payments_connected':settings.PAYMENTS_ENABLED})


@csrf_exempt
@require_POST
@api_errors
def reader_scan(request):
    reader = reader_auth(request)
    if not reader: return JsonResponse({'error':'unauthorized'},status=401)
    data = json.loads(request.body)
    scan = record_scan(reader,data['uid'],uuid.UUID(data['key']),data.get('purpose','balance'))
    response = JsonResponse(scan_data(scan,include_pairing=True))
    response['Cache-Control'] = 'no-store'
    return response


@require_GET
def reader_scan_state(request, key):
    reader = reader_auth(request)
    if not reader: return JsonResponse({'error':'unauthorized'},status=401)
    scan = get_object_or_404(CardScan.objects.select_related('reader','operation'),key=key,reader=reader)
    Reader.objects.filter(pk=reader.pk).update(last_seen=timezone.now())
    response = JsonResponse(scan_data(scan,include_pairing=True))
    response['Cache-Control'] = 'no-store'
    return response


@login_required
@require_POST
@api_errors
def activate(request, preload_id):
    wallet = wallet_for(request.user)
    get_object_or_404(Preload,pk=preload_id,recipient=wallet)
    p = activate_preload(wallet,preload_id)
    return JsonResponse({'id':str(p.pk),'status':p.status,'balance':balance(wallet)})


@staff_member_required
@require_POST
def assign_preload(request):
    from django.contrib.auth import get_user_model
    try:
        user = get_user_model().objects.get(username=request.POST.get('recipient',''),is_active=True)
        p = issue_preload(wallet_for(request.user),wallet_for(user),int(request.POST.get('amount','')),uuid.UUID(request.POST.get('key','')))
        messages.success(request,f'Prerecarga de ${p.amount} CLP reservada para {user.username}. Sin vencimiento configurado.')
    except (ValueError,IntegrityError,get_user_model().DoesNotExist) as e:
        messages.error(request,str(e) if isinstance(e,ValueError) else 'No se pudo asignar: verifica usuario y referencia.')
    return redirect('/ops/')


@staff_member_required
@require_POST
def revoke_preload(request, preload_id):
    issuer = wallet_for(request.user)
    get_object_or_404(Preload,pk=preload_id,issuer=issuer)
    try:
        cancel_preload(issuer,preload_id)
        messages.success(request,'Prerecarga cancelada; fondos devueltos a la cuenta de origen.')
    except ValueError as e: messages.error(request,str(e))
    return redirect('/ops/')


@staff_member_required
@require_GET
def ops_state(request):
    return JsonResponse({'report':reconciliation(),'funding_balance':balance(wallet_for(request.user)),'preloads':[{'id':str(p.pk),'recipient':p.recipient.user.username,'amount':p.amount,'status':p.status,'label':p.get_status_display(),'created_at':p.created_at.isoformat(),'cancellable':p.status=='ready' and p.issuer.user_id==request.user.pk} for p in Preload.objects.select_related('recipient__user','issuer').order_by('-created_at')[:100]],'updated_at':timezone.now().isoformat()})


@staff_member_required
@require_GET
def reader_panel(request):
    now = timezone.now()
    readers = []
    for reader in Reader.objects.all():
        scan = CardScan.objects.filter(reader=reader).order_by('-created_at').first()
        tag = Tag.objects.filter(uid=scan.uid).select_related('wallet__user').first() if scan else None
        online = bool(reader.active and reader.last_seen and (now-reader.last_seen).total_seconds()<45)
        readers.append({'id':reader.pk,'name':reader.name,'online':online,'active':reader.active,
            'last_seen':reader.last_seen.isoformat() if reader.last_seen else None,
            'scan':{'key':str(scan.pk),'uid':scan.uid,'at':scan.created_at.isoformat(),
                    'pairable':online and scan.wallet_id is None and scan.purpose=='balance' and scan.expires_at>now,
                    'card_number':tag.card_number if tag else None,'owner':tag.wallet.user.username if tag else None,
                    'active':tag.active if tag else False} if scan else None,
            'write_supported':False})
    response = JsonResponse({'readers':readers,'requests':[{'id':r.pk,'number':r.card_number,'user':r.wallet.user.username} for r in CardAssociationRequest.objects.filter(status='pending').select_related('wallet__user').order_by('created_at')]})
    response['Cache-Control'] = 'no-store'
    return response


@staff_member_required
@require_POST
def finish_card_association(request):
    from .cards import complete_association
    try:
        tag = complete_association(request.POST.get('request_id'),request.POST.get('scan_key'),request.POST.get('number'),request.user.pk)
        return JsonResponse({'status':'associated','number':tag.card_number})
    except (ValueError,ValidationError,IntegrityError,CardAssociationRequest.DoesNotExist,CardScan.DoesNotExist) as e:
        return JsonResponse({'error':str(e) if isinstance(e,ValueError) else 'Solicitud o lectura no disponible. Actualiza el panel.'},status=409)


@login_required
@require_GET
def transport_state(request):
    response = JsonResponse(Transport().balance(wallet_for(request.user)))
    response['Cache-Control'] = 'no-store, private'
    return response
