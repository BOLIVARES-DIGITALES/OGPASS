import hashlib, hmac, time
from urllib.parse import urlparse
import requests
from django.conf import settings
from django.utils import timezone

class IntegrationError(Exception): pass

class MercadoPago:
    base = 'https://api.mercadopago.com'
    def request(self, method, path, **kwargs):
        if not settings.PAYMENTS_ENABLED: raise IntegrationError('Medio de pago no conectado')
        try:
            response = requests.request(method,self.base+path,headers={'Authorization':f'Bearer {settings.MP_ACCESS_TOKEN}'},timeout=15,**kwargs)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException,ValueError) as exc:
            raise IntegrationError('Mercado Pago no respondió; vuelva a intentar') from exc
    def checkout(self, topup):
        data = self.request('POST','/checkout/preferences',json={
            'items':[{'id':str(topup.pk),'title':'Recarga OGPASS CLP','quantity':1,'currency_id':'CLP','unit_price':topup.amount}],
            'external_reference':str(topup.pk),'notification_url':settings.PUBLIC_URL+'/api/payments/webhook/',
            'back_urls':{s:settings.PUBLIC_URL+'/' for s in ['success','pending','failure']},'auto_return':'approved',
            'payment_methods':{'installments':1}})
        url = data['init_point']
        if urlparse(url).scheme != 'https' or urlparse(url).hostname not in ('www.mercadopago.cl','www.mercadopago.com','www.mercadopago.com.ar'):
            raise IntegrationError('Checkout host inesperado')
        return str(data['id']),url
    def payment(self, payment_id):
        if not str(payment_id).isdigit(): raise ValueError('Invalid payment id')
        return self.request('GET',f'/v1/payments/{payment_id}')
    def verify(self, request):
        if not settings.PAYMENTS_ENABLED: return False
        parts = dict(p.strip().split('=',1) for p in request.headers.get('x-signature','').split(',') if '=' in p)
        ts, signature = parts.get('ts',''),parts.get('v1','')
        data_id = request.GET.get('data.id','').lower()
        request_id = request.headers.get('x-request-id','')
        if not ts.isdigit() or not data_id.isdigit() or not request_id: return False
        # MP timestamps may use seconds or milliseconds. Retries receive a fresh signature.
        stamp = int(ts) / (1000 if len(ts)>10 else 1)
        if abs(time.time()-stamp) > 600: return False
        manifest = f'id:{data_id};request-id:{request_id};ts:{ts};'
        expected = hmac.new(settings.MP_WEBHOOK_SECRET.encode(),manifest.encode(),hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected,signature)

class Transport:
    """Public portal availability only; never manufactures a balance or bypasses its challenge."""
    source_url = 'https://www.tarjetabip.cl/testPOCAE.php'
    portal_url = 'http://pocae.tstgo.cl/PortalCAE-WAR-MODULE/'

    def portal_status(self):
        from django.core.cache import cache
        key = 'bip-public-portal-v1'
        cached = cache.get(key)
        if cached: return cached
        result = {'status':'unavailable','checked_at':timezone.now().isoformat()}
        try:
            # Fixed official destination, no card number or account data transmitted.
            response = requests.get(self.portal_url,timeout=(3,5),allow_redirects=False)
            response.raise_for_status()
            html = response.text
            if response.status_code == 200 and 'txtNumTarjeta' in html and 'defaultReal' in html and 'realperson' in html:
                result['status'] = 'verification_required'
            elif response.status_code == 200:
                result['status'] = 'integration_required'
        except requests.RequestException:
            pass
        cache.set(key,result,300)
        return result

    def balance(self, wallet):
        from .models import Tag, CardAssociationRequest
        numbers = list(Tag.objects.filter(wallet=wallet,active=True).exclude(card_number='').values_list('card_number',flat=True))
        numbers += list(CardAssociationRequest.objects.filter(wallet=wallet,status='pending').values_list('card_number',flat=True))
        numbers = list(dict.fromkeys(numbers))
        status = self.portal_status() if numbers else {'status':'no_card','checked_at':None}
        messages = {
            'verification_required':'El portal oficial exige completar una verificación visual (CAPTCHA). Abre la consulta oficial e introduce tu número. OGPASS todavía no puede recuperar ese resultado automáticamente.',
            'unavailable':'No pudimos comprobar la disponibilidad del portal oficial. Puedes intentar abrirlo directamente. No hay saldo verificado.',
            'integration_required':'La consulta automática no está conectada. Consulta el saldo directamente en el portal oficial.',
            'no_card':'Guarda el número de tu tarjeta para acceder a la consulta oficial.'}
        return {**status,'source':'Portal oficial tarjeta bip!','source_url':self.source_url,
                'balance':None,'updated_at':None,'message':messages[status['status']],
                'cards':[{'card_number':n,'balance':None,'status':status['status']} for n in numbers]}

class Stellar:
    def balance(self, account):
        base = settings.STELLAR_TESTNET_URL if account.network == 'testnet' else settings.STELLAR_MAINNET_URL
        try:
            r = requests.get(base+'/accounts/'+account.address,timeout=5)
            if r.status_code == 404: return {'status':'unfunded','network':account.network,'address':account.address,'balances':[]}
            r.raise_for_status()
            return {'status':'connected','network':account.network,'address':account.address,'balances':r.json()['balances'],'updated_at':timezone.now().isoformat(),'source_url':base+'/accounts/'+account.address}
        except (requests.RequestException,ValueError,KeyError):
            return {'status':'unavailable','network':account.network,'address':account.address,'balances':[],'updated_at':None}
