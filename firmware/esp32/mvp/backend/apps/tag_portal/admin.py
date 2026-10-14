from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.html import format_html
from core.models import Audit
from .models import TagPortal
from .services import payload_info, portal_path


@admin.register(TagPortal)
class TagPortalAdmin(admin.ModelAdmin):
    list_display = ['id', 'enabled', 'tag', 'activated_at', 'theme']
    list_filter = ['enabled', 'theme']
    fields = ['code', 'public_link', 'tag', 'enabled', 'title', 'message', 'theme', 'activated_at']
    readonly_fields = ['code', 'public_link', 'activated_at']

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (['tag'] if obj and obj.tag_id else [])

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for field in ('title', 'message'):
            if field in form.base_fields:
                form.base_fields[field].help_text = 'Texto PÚBLICO. No incluir datos personales, saldo ni información del titular.'
        if 'tag' in form.base_fields:
            form.base_fields['tag'].help_text = 'Solo tarjetas ya asociadas mediante el flujo físico verificado. Dejar vacío para inventario nuevo.'
        return form

    @admin.display(description='Enlace NFC / QR')
    def public_link(self, obj):
        if not obj.pk:
            return 'Disponible después de guardar.'
        try:
            payload = payload_info(obj)
        except ValidationError:
            return 'Revisar PUBLIC_URL.'
        return format_html('<a href="{}">{}</a> · {} bytes · NTAG213: {}',
                           portal_path(obj), payload['uri'], payload['ntag213_bytes'],
                           'cabe' if payload['fits_ntag213'] else 'excede capacidad')

    def has_delete_permission(self, request, obj=None):
        return False

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if change:
            original = TagPortal.objects.select_for_update().get(pk=obj.pk)
            if original.tag_id and original.tag_id != obj.tag_id:
                raise ValidationError('Un enlace asignado no puede transferirse a otra tarjeta.')
        super().save_model(request, obj, form, change)
        Audit.objects.create(actor=str(request.user.pk), event='tag_portal_configured',
                             reference=str(obj.pk), details={'fields': form.changed_data})
