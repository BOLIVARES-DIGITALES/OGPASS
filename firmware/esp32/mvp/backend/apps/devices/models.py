import uuid
from django.conf import settings
from django.db import models


class OgpassDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reader = models.OneToOneField('core.Reader', on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    device_type = models.CharField(max_length=32, default='ESP32')
    driver = models.CharField(max_length=32, default='rc522')
    firmware_version = models.CharField(max_length=40, blank=True)
    capabilities = models.JSONField(default=list)
    health = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'


class HardwareEvent(models.Model):
    event_id = models.UUIDField(primary_key=True, editable=False)
    request_id = models.UUIDField()
    device = models.ForeignKey(OgpassDevice, on_delete=models.PROTECT)
    credential = models.ForeignKey('core.NormalizedCredential', null=True, on_delete=models.PROTECT)
    scan = models.OneToOneField('core.CardScan', null=True, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=32)
    metadata = models.JSONField(default=dict)
    observed_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

