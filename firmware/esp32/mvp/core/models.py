import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q

class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    frozen = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.user.username

class Tag(models.Model):
    uid = models.CharField(max_length=32, unique=True)
    card_number = models.CharField(max_length=12, blank=True)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Reader(models.Model):
    name = models.CharField(max_length=64, unique=True)
    token_hash = models.CharField(max_length=128)
    active = models.BooleanField(default=True)
    amount = models.PositiveIntegerField(default=1000)
    cost = models.PositiveIntegerField(default=700)
    last_seen = models.DateTimeField(null=True, blank=True)
    last_uid = models.CharField(max_length=32, blank=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name='reader_positive_price'),models.CheckConstraint(condition=Q(cost__lt=models.F('amount')),name='reader_positive_margin')]

class Journal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=160, unique=True)
    kind = models.CharField(max_length=32)
    actor = models.CharField(max_length=160)
    reversal_of = models.OneToOneField('self',null=True,blank=True,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

class Entry(models.Model):
    journal = models.ForeignKey(Journal,related_name='entries',on_delete=models.PROTECT)
    account = models.CharField(max_length=80)
    # Signed integer CLP: debit positive, credit negative.
    amount = models.BigIntegerField()
    class Meta:
        constraints = [models.CheckConstraint(condition=~Q(amount=0), name='nonzero_entry')]

class TopUp(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    wallet = models.ForeignKey(Wallet,on_delete=models.PROTECT)
    key = models.UUIDField(unique=True)
    amount = models.PositiveIntegerField()
    status = models.CharField(max_length=32,default='pending')
    payment_id = models.CharField(max_length=64,unique=True,null=True,blank=True)
    checkout_url = models.URLField(blank=True)
    preference_id = models.CharField(max_length=100,blank=True)
    fee = models.PositiveIntegerField(default=0)
    journal = models.OneToOneField(Journal,null=True,blank=True,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

class Operation(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    key = models.UUIDField(unique=True)
    reader = models.ForeignKey(Reader,on_delete=models.PROTECT)
    wallet = models.ForeignKey(Wallet,null=True,on_delete=models.PROTECT)
    uid = models.CharField(max_length=32)
    amount = models.PositiveIntegerField()
    cost = models.PositiveIntegerField()
    status = models.CharField(max_length=32,default='pending')
    reason = models.CharField(max_length=160,blank=True)
    journal = models.OneToOneField(Journal,null=True,blank=True,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    @property
    def margin(self): return self.amount-self.cost if self.status == 'approved' else 0

class Audit(models.Model):
    actor = models.CharField(max_length=160)
    event = models.CharField(max_length=80)
    reference = models.CharField(max_length=160)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

class StellarAccount(models.Model):
    wallet = models.ForeignKey(Wallet,on_delete=models.PROTECT)
    network = models.CharField(max_length=10,choices=[('testnet','Testnet'),('mainnet','Mainnet')])
    address = models.CharField(max_length=56)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['wallet','network'], name='wallet_stellar_network')]

class RateBucket(models.Model):
    key = models.CharField(max_length=64,primary_key=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()


class CardScan(models.Model):
    key = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reader = models.ForeignKey(Reader, on_delete=models.PROTECT)
    uid = models.CharField(max_length=32)
    purpose = models.CharField(max_length=10, choices=[('balance','Saldo'),('payment','Pago')], default='balance')
    wallet = models.ForeignKey(Wallet, null=True, blank=True, on_delete=models.PROTECT)
    pairing_hash = models.CharField(max_length=64, unique=True, null=True, blank=True)
    paired_at = models.DateTimeField(null=True, blank=True)
    operation = models.OneToOneField(Operation, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()


class Preload(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.UUIDField(unique=True)
    issuer = models.ForeignKey(Wallet, related_name='issued_preloads', on_delete=models.PROTECT)
    recipient = models.ForeignKey(Wallet, related_name='received_preloads', on_delete=models.PROTECT)
    amount = models.PositiveIntegerField()
    status = models.CharField(max_length=12, default='ready', choices=[('ready','Por activar'),('activated','Activada'),('cancelled','Cancelada')])
    reserve_journal = models.OneToOneField(Journal, related_name='+', on_delete=models.PROTECT)
    settlement_journal = models.OneToOneField(Journal, related_name='+', null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name='positive_preload')]


class WalletEvent(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    kind = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        indexes = [models.Index(fields=['wallet','id'])]


class CardAssociationRequest(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT)
    card_number = models.CharField(max_length=9)
    status = models.CharField(max_length=12, default='pending')
    tag = models.ForeignKey(Tag, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['wallet'], condition=Q(status='pending'), name='one_pending_card_request')]
