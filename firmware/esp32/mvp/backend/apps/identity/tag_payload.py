"""Signed, expiring application reference. Never a payment authorization."""
from django.core import signing
from backend.apps.credentials.models import NormalizedCredential

SALT = 'ogpass.tag.reference.v1'


def issue(credential):
    if not credential.identity_id or credential.status != 'active' or (credential.tag_id and not credential.tag.active):
        raise ValueError('Inactive credential')
    return signing.dumps({'version': 1, 'public_id': str(credential.identity.public_id),
                          'credential_id': str(credential.pk),
                          'wallet_reference': str(credential.identity.wallet_id),
                          'token_reference': str(credential.identity.token_id),
                          'purpose': 'profile_reference'}, salt=SALT, compress=True)


def verify(payload, max_age=300):
    data = signing.loads(payload, salt=SALT, max_age=max_age)
    credential = NormalizedCredential.objects.select_related('identity', 'tag').get(pk=data['credential_id'])
    if (credential.status != 'active' or (credential.tag_id and not credential.tag.active)
            or data['public_id'] != str(credential.identity.public_id)):
        raise signing.BadSignature('Credential revoked')
    return credential

