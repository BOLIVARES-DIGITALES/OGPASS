import hashlib,secrets
from django.core.management.base import BaseCommand,CommandError
from core.models import Reader,Audit
class Command(BaseCommand):
    help = 'Provisiona o rota el token del lector; se muestra una sola vez.'
    def add_arguments(self,p):
        p.add_argument('--name',default='ESP32-001');p.add_argument('--amount',type=int,default=1000);p.add_argument('--cost',type=int,default=700)
    def handle(self,*a,**o):
        if not 0 <= o['cost'] < o['amount']: raise CommandError('Se requiere precio > costo >= 0')
        token=secrets.token_urlsafe(32)
        reader,_=Reader.objects.update_or_create(name=o['name'],defaults={'token_hash':hashlib.sha256(token.encode()).hexdigest(),'amount':o['amount'],'cost':o['cost'],'active':True})
        Audit.objects.create(actor='cli',event='reader_provisioned',reference=str(reader.pk))
        self.stdout.write('READER_TOKEN='+token)
