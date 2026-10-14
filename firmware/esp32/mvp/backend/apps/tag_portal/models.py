"""Public routing handles. These are never authentication or payment tokens."""
import secrets
from django.core.validators import RegexValidator
from django.db import models


def public_code():
    return secrets.token_urlsafe(24)


class TagPortal(models.Model):
    code = models.CharField(max_length=32, unique=True, default=public_code, editable=False,
                           validators=[RegexValidator(r'^[A-Za-z0-9_-]{32}$')])
    tag = models.OneToOneField('core.Tag', null=True, blank=True, on_delete=models.PROTECT,
                              related_name='portal')
    enabled = models.BooleanField(default=True)
    title = models.CharField(max_length=80, default='Tu acceso a OGPASS')
    message = models.CharField(max_length=240, default='Un llavero para acceder a tu cuenta. Tus datos permanecen privados.')
    theme = models.CharField(max_length=10, choices=[('light', 'Claro'), ('dark', 'Oscuro')], default='light')
    activated_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'

    def __str__(self):
        return f'Portal {self.pk or "nuevo"}'
