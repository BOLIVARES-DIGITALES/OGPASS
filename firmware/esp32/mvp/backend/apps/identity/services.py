from django.db import transaction
from core.models import Wallet
from .models import OgpassIdentity


@transaction.atomic
def identity_for(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return OgpassIdentity.objects.get_or_create(user=user, defaults={'wallet': wallet})[0]


def identity_data(identity):
    # PRIVATE_ID is deliberately never included in serializers or payloads.
    return {'public_id': str(identity.public_id), 'wallet_id': identity.wallet_id,
            'token_id': str(identity.token_id), 'token_status': 'reference_only'}

