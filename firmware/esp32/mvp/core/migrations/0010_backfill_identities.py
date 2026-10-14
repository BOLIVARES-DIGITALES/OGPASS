import uuid
from django.conf import settings
from django.db import migrations


def backfill(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    Wallet = apps.get_model('core', 'Wallet')
    Identity = apps.get_model('core', 'OgpassIdentity')
    db = schema_editor.connection.alias
    for user_id in User.objects.using(db).values_list('pk', flat=True).iterator():
        wallet, _ = Wallet.objects.using(db).get_or_create(user_id=user_id)
        Identity.objects.using(db).get_or_create(user_id=user_id, defaults={
            'wallet_id': wallet.pk, 'public_id': uuid.uuid4(),
            'private_id': uuid.uuid4(), 'token_id': uuid.uuid4()})


class Migration(migrations.Migration):
    dependencies = [('core', '0009_ogpassdevice_normalizedcredential_hardwareevent_and_more')]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
