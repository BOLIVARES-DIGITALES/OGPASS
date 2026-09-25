import json
from django.core.management.base import BaseCommand
from core.models import StellarAccount
from core.adapters import Stellar
class Command(BaseCommand):
    def add_arguments(self,p):p.add_argument('username')
    def handle(self,*a,**o):
        results=[Stellar().balance(account) for account in StellarAccount.objects.filter(wallet__user__username=o['username'])]
        self.stdout.write(json.dumps(results,indent=2))
