import hashlib,time
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from .models import RateBucket
class RateLimitMiddleware:
    """Shared PostgreSQL counters, independent of worker count."""
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        limits={'/login/':20,'/admin/login/':20,'/register/':5,'/topups/':10,'/tags/':10,'/ops/preloads/':10,'/api/reader/touch/':40,'/api/reader/scans/':40}
        limits.update({'/api/v1/credentials/scan/':40, '/api/v1/credentials/assign/':10, '/api/v1/devices/register/':10, '/api/v1/devices/heartbeat/':30})
        portal_path = request.path.startswith(('/w/', '/api/v1/tags/', '/my/tags/'))
        bucket_path = request.path
        limit = limits.get(request.path) if request.method == 'POST' else None
        if portal_path and request.method in ('GET', 'POST'):
            # Group dynamic codes: rotating the URL must not reset throttling.
            bucket_path = 'tag-portal:' + request.method
            limit = 10 if request.method == 'POST' else 120
        if limit is not None:
            # Backend is only reachable through Caddy in production; Caddy replaces XFF.
            ip=request.META.get('REMOTE_ADDR','unknown') if settings.DEBUG else request.headers.get('X-Forwarded-For',request.META.get('REMOTE_ADDR','unknown')).split(',')[-1].strip()
            key=hashlib.sha256(f'{ip}:{bucket_path}:{int(time.time())//60}'.encode()).hexdigest()
            with transaction.atomic():
                bucket,_=RateBucket.objects.get_or_create(key=key,defaults={'expires_at':timezone.now()+timedelta(minutes=2)})
                bucket=RateBucket.objects.select_for_update().get(pk=key)
                bucket.count+=1;bucket.save(update_fields=['count'])
                exceeded=bucket.count>limit
            if exceeded:
                return self.protect(request, JsonResponse({'error':'Demasiados intentos; espere un minuto'},status=429,headers={'Retry-After':'60'}))
        response=self.get_response(request)
        return self.protect(request, response)

    @staticmethod
    def protect(request, response):
        if request.path.startswith(('/api/v1/','/api/state/','/api/session/','/api/external/','/api/ops/','/ops/','/w/','/my/tags/')) or request.path=='/':
            response['Cache-Control']='no-store, private'
        if request.path.startswith(('/w/', '/api/v1/tags/', '/my/tags/')):
            # Keep same-origin form Origin/Referer checks intact; never send
            # the tag URL to a different origin.
            response['Referrer-Policy']='same-origin'
            response['X-Robots-Tag']='noindex, nofollow'
        if request.path.startswith('/w/'):
            response['Content-Security-Policy']="default-src 'none'; style-src 'self'; img-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
        return response
