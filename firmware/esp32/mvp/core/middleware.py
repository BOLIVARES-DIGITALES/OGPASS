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
        if request.method=='POST' and request.path in limits:
            # Backend is only reachable through Caddy in production; Caddy replaces XFF.
            ip=request.META.get('REMOTE_ADDR','unknown') if settings.DEBUG else request.headers.get('X-Forwarded-For',request.META.get('REMOTE_ADDR','unknown')).split(',')[-1].strip()
            key=hashlib.sha256(f'{ip}:{request.path}:{int(time.time())//60}'.encode()).hexdigest()
            with transaction.atomic():
                bucket,_=RateBucket.objects.get_or_create(key=key,defaults={'expires_at':timezone.now()+timedelta(minutes=2)})
                bucket=RateBucket.objects.select_for_update().get(pk=key)
                bucket.count+=1;bucket.save(update_fields=['count'])
                exceeded=bucket.count>limits[request.path]
            if exceeded:return JsonResponse({'error':'Demasiados intentos; espere un minuto'},status=429,headers={'Retry-After':'60'})
        response=self.get_response(request)
        if request.path.startswith(('/api/state/','/api/external/','/api/ops/','/ops/')) or request.path=='/':
            response['Cache-Control']='no-store, private'
        return response
