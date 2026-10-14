import uuid
from django.db import models


class NormalizedCredential(models.Model):
    credential_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.ForeignKey('core.OgpassIdentity', null=True, on_delete=models.PROTECT)
    tag = models.OneToOneField('core.Tag', null=True, on_delete=models.PROTECT)
    technology = models.CharField(max_length=24)
    protocol = models.CharField(max_length=32)
    source = models.CharField(max_length=32)
    identifier_hash = models.CharField(max_length=64, unique=True)
    uid = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict)
    capabilities = models.JSONField(default=list)
    device = models.ForeignKey('core.OgpassDevice', null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(null=True)
    status = models.CharField(max_length=24, default='unassigned')

    class Meta:
        app_label = 'core'

