import hashlib
from django.db import transaction
from core.models import Tag
from backend.apps.identity.services import identity_for
from .models import NormalizedCredential


@transaction.atomic
def sync_tag(tag):
    identity = identity_for(tag.wallet.user)
    digest = hashlib.sha256(f'NFC:ISO14443A:{tag.uid}'.encode()).hexdigest()
    credential, _ = NormalizedCredential.objects.get_or_create(
        identifier_hash=digest,
        defaults={'technology': 'NFC', 'protocol': 'ISO14443A', 'uid': tag.uid,
                  'source': 'legacy', 'capabilities': ['IDENTIFY', 'READ']})
    if credential.identity_id and credential.identity_id != identity.pk:
        from core.services import Conflict
        raise Conflict('La credencial ya tiene otro titular')
    credential.identity, credential.tag = identity, tag
    credential.status = 'active' if tag.active else 'disabled'
    credential.save(update_fields=['identity', 'tag', 'status'])
    return credential


def credentials_for(user):
    # Preserve credentials created via all existing association APIs.
    for tag in Tag.objects.filter(wallet__user=user).select_related('wallet__user'):
        sync_tag(tag)
    return NormalizedCredential.objects.filter(identity__user=user).select_related('tag')


def credential_data(credential, developer=False):
    data = {'credential_id': str(credential.pk),
            'owner_public_id': str(credential.identity.public_id) if credential.identity_id else None,
            'technology': credential.technology, 'status': 'disabled' if credential.tag_id and not credential.tag.active else credential.status,
            'created_at': credential.created_at.isoformat(),
            'last_seen': credential.last_seen.isoformat() if credential.last_seen else None,
            'device_id': str(credential.device_id) if credential.device_id else None}
    if developer:
        data.update(uid=credential.uid, protocol=credential.protocol, source=credential.source,
                    metadata=credential.metadata, capabilities=credential.capabilities)
    return data

