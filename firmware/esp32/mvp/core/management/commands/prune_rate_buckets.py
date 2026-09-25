from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import RateBucket
class Command(BaseCommand):
    def handle(self,*args,**options):
        count,_=RateBucket.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(str(count)+' expired rate buckets removed')
