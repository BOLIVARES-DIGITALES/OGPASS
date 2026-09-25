from django.db import migrations

SQL='''
CREATE TABLE ogpass_journal_seal (journal_id uuid PRIMARY KEY);
INSERT INTO ogpass_journal_seal SELECT id FROM core_journal;
CREATE TRIGGER immutable_seal BEFORE UPDATE OR DELETE ON ogpass_journal_seal FOR EACH ROW EXECUTE FUNCTION ogpass_immutable();
CREATE FUNCTION ogpass_no_late_entries() RETURNS trigger AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM ogpass_journal_seal WHERE journal_id=NEW.journal_id) THEN
    RAISE EXCEPTION 'OGPASS cannot append to a committed journal';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER no_late_entries BEFORE INSERT ON core_entry FOR EACH ROW EXECUTE FUNCTION ogpass_no_late_entries();
CREATE OR REPLACE FUNCTION ogpass_balanced() RETURNS trigger SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE jid uuid;
BEGIN
  IF TG_TABLE_NAME = 'core_journal' THEN jid := NEW.id; ELSE jid := NEW.journal_id; END IF;
  IF (SELECT COUNT(*) FROM core_entry WHERE journal_id=jid) < 2 OR
     (SELECT COALESCE(SUM(amount),0) FROM core_entry WHERE journal_id=jid) <> 0 THEN
    RAISE EXCEPTION 'OGPASS unbalanced journal %', jid;
  END IF;
  INSERT INTO ogpass_journal_seal VALUES (jid) ON CONFLICT DO NOTHING;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ogpass') THEN
    REVOKE INSERT, UPDATE, DELETE ON ogpass_journal_seal FROM ogpass;
  END IF;
END $$;
'''
def apply(apps,editor):
    if editor.connection.vendor=='postgresql':editor.execute(SQL,params=None)
class Migration(migrations.Migration):
    dependencies=[('core','0003_ratebucket')]
    operations=[migrations.RunPython(apply)]
