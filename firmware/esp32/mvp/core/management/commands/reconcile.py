import json
from django.core.management.base import BaseCommand,CommandError
from core.services import reconciliation
class Command(BaseCommand):
    def handle(self,*a,**o):
        result=reconciliation()
        self.stdout.write(json.dumps(result,indent=2))
        if result['trial_balance'] or result['unbalanced_journals']: raise CommandError('Ledger desbalanceado')
