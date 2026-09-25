import os
from pathlib import Path
import requests
from stellar_sdk import Keypair
from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth import get_user_model
from core.models import Wallet,StellarAccount,Audit
class Command(BaseCommand):
    help = 'Crea cuenta Testnet con Friendbot o asocia una dirección pública Mainnet de solo lectura.'
    def add_arguments(self,p):
        p.add_argument('username');p.add_argument('--network',choices=['testnet','mainnet'],default='testnet');p.add_argument('--address');p.add_argument('--secret-file')
    def handle(self,*a,**o):
        try: user=get_user_model().objects.get(username=o['username'])
        except get_user_model().DoesNotExist: raise CommandError('Usuario inexistente')
        wallet,_=Wallet.objects.get_or_create(user=user)
        account=StellarAccount.objects.filter(wallet=wallet,network=o['network']).first()
        if not account:
            address=o['address']
            if not address:
                if o['network']=='mainnet': raise CommandError('Mainnet requiere --address; no crea ni fondea cuentas')
                if not o['secret_file']: raise CommandError('Indique --secret-file fuera del código para guardar la clave (modo 0600)')
                kp=Keypair.random()
                fd=os.open(o['secret_file'],os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'w') as f:f.write(kp.secret+'\n')
                address=kp.public_key
            try: Keypair.from_public_key(address)
            except Exception: raise CommandError('Dirección Stellar inválida')
            account=StellarAccount.objects.create(wallet=wallet,network=o['network'],address=address)
            Audit.objects.create(actor='cli',event='stellar_account_linked',reference=address,details={'network':o['network']})
        self.stdout.write(f'{account.network}: {account.address}')
        if account.network=='testnet':
            try:
                r=requests.get('https://horizon-testnet.stellar.org/accounts/'+account.address,timeout=15)
                if r.status_code==404:
                    r=requests.get('https://friendbot.stellar.org',params={'addr':account.address},timeout=30)
                r.raise_for_status()
            except requests.RequestException as e: raise CommandError('Cuenta guardada, fondeo no verificado. Reejecute el mismo comando para reintentar.') from e
            self.stdout.write('Testnet verificado. XLM de prueba, sin valor real.')
