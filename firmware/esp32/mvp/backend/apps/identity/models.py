import uuid
from django.conf import settings
from django.db import models


class OgpassIdentity(models.Model):
    """References only: neither these UUIDs nor a tag authorize a debit."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    wallet = models.OneToOneField('core.Wallet', on_delete=models.PROTECT)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    private_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    token_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'

