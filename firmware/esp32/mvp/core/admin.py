from django.contrib import admin
from .models import Wallet,Tag,Reader,Journal,Entry,TopUp,Operation,Audit,StellarAccount,CardScan,Preload
class ReadOnly(admin.ModelAdmin):
    def has_add_permission(self,r): return False
    def has_change_permission(self,r,obj=None): return False
    def has_delete_permission(self,r,obj=None): return False
for model in [Journal,Entry,TopUp,Operation,Audit,StellarAccount,CardScan,Preload]: admin.site.register(model,ReadOnly)
@admin.register(Reader)
class ReaderAdmin(admin.ModelAdmin):
    fields = ['name','active','amount','cost','last_seen','last_uid']
    readonly_fields = ['last_seen','last_uid']
    list_display = ['name','active','amount','cost','last_seen']
    def has_add_permission(self,r): return False
    def has_delete_permission(self,r,obj=None): return False
    def save_model(self,r,obj,form,change):
        super().save_model(r,obj,form,change)
        Audit.objects.create(actor=str(r.user.pk),event='reader_updated',reference=str(obj.pk),details={'fields':form.changed_data})
@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    readonly_fields = ['user','created_at']
    def has_add_permission(self,r): return False
    def has_delete_permission(self,r,obj=None): return False
    def save_model(self,r,obj,form,change):
        super().save_model(r,obj,form,change)
        Audit.objects.create(actor=str(r.user.pk),event='wallet_updated',reference=str(obj.pk),details={'frozen':obj.frozen})
        from .realtime import emit_event
        emit_event(obj.pk,'wallet_updated')
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    readonly_fields = ['uid','card_number','wallet','created_at']
    def has_add_permission(self,r): return False
    def has_delete_permission(self,r,obj=None): return False
    def save_model(self,r,obj,form,change):
        super().save_model(r,obj,form,change)
        Audit.objects.create(actor=str(r.user.pk),event='tag_updated',reference=obj.uid,details={'active':obj.active})
        from .realtime import emit_event
        emit_event(obj.wallet_id,'tag_updated')
admin.site.site_header = 'OGPASS · Administración'
