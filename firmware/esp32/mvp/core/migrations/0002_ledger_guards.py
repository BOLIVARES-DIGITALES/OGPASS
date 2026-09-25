from django.db import migrations

SQL = '''
CREATE FUNCTION ogpass_immutable() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'OGPASS ledger and audit records are immutable'; END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER immutable_entry BEFORE UPDATE OR DELETE ON core_entry FOR EACH ROW EXECUTE FUNCTION ogpass_immutable();
CREATE TRIGGER immutable_journal BEFORE UPDATE OR DELETE ON core_journal FOR EACH ROW EXECUTE FUNCTION ogpass_immutable();
CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON core_audit FOR EACH ROW EXECUTE FUNCTION ogpass_immutable();
CREATE FUNCTION ogpass_balanced() RETURNS trigger AS $$
DECLARE jid uuid;
BEGIN
  IF TG_TABLE_NAME = 'core_journal' THEN jid := NEW.id; ELSE jid := NEW.journal_id; END IF;
  IF (SELECT COUNT(*) FROM core_entry WHERE journal_id=jid) < 2 OR
     (SELECT COALESCE(SUM(amount),0) FROM core_entry WHERE journal_id=jid) <> 0 THEN
    RAISE EXCEPTION 'OGPASS unbalanced journal %', jid;
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER balanced_entry AFTER INSERT ON core_entry DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ogpass_balanced();
CREATE CONSTRAINT TRIGGER balanced_journal AFTER INSERT ON core_journal DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ogpass_balanced();
'''
def forward(apps, editor):
    if editor.connection.vendor == 'postgresql': editor.execute(SQL, params=None)
def backward(apps, editor):
    if editor.connection.vendor == 'postgresql':
        editor.execute('DROP FUNCTION ogpass_immutable() CASCADE; DROP FUNCTION ogpass_balanced() CASCADE;')
class Migration(migrations.Migration):
    dependencies = [('core','0001_initial')]
    operations = [migrations.RunPython(forward,backward)]
