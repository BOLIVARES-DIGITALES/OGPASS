# Guía de sincronización OGPASS ↔ Supabase

## Objetivo

Usar Supabase como PostgreSQL administrado para OGPASS, manteniendo Django como única autoridad para usuarios, lectores, saldos, auditoría y ledger. Lovable no debe escribir directamente las tablas financieras.

## 0. Confirmar el proyecto correcto antes de migrar

La captura muestra el proyecto `OGPASS` con URL:

```text
https://ynisiarxjpgdxapmoppp.supabase.co
```

Su referencia es:

```text
ynisiarxjpgdxapmoppp
```

El repositorio ya quedó alineado en `front_ogpass-sdk-hub/supabase/config.toml` con `ynisiarxjpgdxapmoppp`. Esta debe permanecer como referencia única para Lovable, el frontend y cualquier uso de Supabase CLI.

## 1. Obtener la conexión PostgreSQL desde el Home mostrado

1. En la parte superior, pulsar el botón verde **Connect**.
2. Seleccionar **Session pooler**. En un plan Free es la opción indicada para un backend Django que se ejecuta desde una red IPv4.
3. Abrir **View parameters** si aparece contraído.
4. Copiar por separado:
   - Host: copiar exactamente; no construirlo manualmente.
   - Port: `5432`.
   - Database: normalmente `postgres`.
   - User: normalmente `postgres.ynisiarxjpgdxapmoppp`.
   - Password: la contraseña de base de datos elegida al crear el proyecto.
5. Si no se recuerda la contraseña: menú izquierdo **Database → Settings → Database password → Reset**. Después del cambio, actualizar inmediatamente cualquier servicio conectado.

No usar aquí Project URL, publishable key, `anon`, secret key ni `service_role`: ninguna de ellas es una contraseña PostgreSQL.

## 2. Preparar el archivo privado local

En Terminal:

```bash
cd /Users/dgitalescss/Desktop/OGPASS/firmware/esp32/mvp
cp supabase.env.example .env.supabase
chmod 600 .env.supabase
nano .env.supabase
```

Completar sin publicar ni enviar por chat:

```dotenv
POSTGRES_HOST=HOST_EXACTO_COPIADO_DE_SESSION_POOLER
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=postgres.ynisiarxjpgdxapmoppp
POSTGRES_PASSWORD=CONTRASENA_DE_BASE_DE_DATOS
POSTGRES_SSLMODE=require
POSTGRES_CONN_MAX_AGE=0
POSTGRES_DISABLE_SERVER_SIDE_CURSORS=1
```

Mantener:

```dotenv
DOMAIN=api.ogpass.xyz
PUBLIC_URL=https://api.ogpass.xyz
ALLOWED_HOSTS=api.ogpass.xyz,localhost,127.0.0.1
```

Generar tres secretos distintos para `SECRET_KEY`, `CREDENTIAL_ENCRYPTION_KEY` y `CREDENTIAL_HMAC_KEY`:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Ejecutar el comando tres veces. No reutilizar valores.

## 3. Validar sin conectarse ni mostrar secretos

```bash
cd /Users/dgitalescss/Desktop/OGPASS/firmware/esp32/mvp
docker build -t ogpass-mvp .
docker run --rm --env-file .env.supabase \
  ogpass-mvp python deploy/preflight_supabase.py
```

Resultado esperado:

```text
Supabase deployment config: OK (secrets were not displayed).
```

Si aparece `tenant or user not found`, volver a **Connect → Session pooler** y copiar nuevamente host y usuario completos. El usuario del pooler incluye la referencia del proyecto.

## 4. Aplicar las migraciones Django

No crear tablas manualmente en **Table Editor** y no usar `supabase db push`: el esquema fuente de OGPASS son las migraciones Django de `firmware/esp32/mvp/core/migrations`.

```bash
docker run --rm --env-file .env.supabase \
  ogpass-mvp python manage.py migrate --noinput
```

Después, en el panel Supabase:

1. Abrir **Table Editor** en el menú izquierdo.
2. Actualizar la página.
3. Confirmar que aparecen, entre otras:
   - `django_migrations`
   - `auth_user`
   - `django_session`
   - `core_wallet`
   - `core_reader`
   - `core_journal`
   - `core_entry`
   - `core_externaltransitcredential`
   - `core_externaltransitbalancesnapshot`

La tarjeta **Last migration** del Home puede tardar en reflejar migraciones que no fueron administradas por Supabase CLI. La evidencia válida es `django_migrations` y la salida exitosa de `manage.py migrate`.

## 5. Bloquear acceso directo a las tablas financieras

El frontend actual utiliza Supabase para autenticación, pero no consulta tablas mediante `supabase.from(...)`. En esta fase, la opción más segura es:

1. Abrir **Integrations → Data API**.
2. Desactivar **Enable Data API** si ninguna función de Lovable depende de REST/GraphQL de Supabase.
3. Si se mantiene Data API activa, abrir **SQL Editor → New query** y ejecutar:

```sql
revoke all privileges on all tables in schema public
from anon, authenticated, service_role;

revoke all privileges on all sequences in schema public
from anon, authenticated, service_role;

alter default privileges for role postgres in schema public
revoke select, insert, update, delete on tables
from anon, authenticated, service_role;

alter default privileges for role postgres in schema public
revoke usage, select on sequences
from anon, authenticated, service_role;

alter default privileges for role postgres in schema public
revoke execute on functions
from anon, authenticated, service_role;
```

Esto no impide que Django se conecte con la cuenta PostgreSQL configurada. Sí impide que una clave pública del navegador permita acceder al ledger.

## 6. Verificación de solo lectura en SQL Editor

En **SQL Editor → New query**:

```sql
select app, name, applied
from django_migrations
order by applied desc
limit 20;

select tablename
from pg_tables
where schemaname = 'public'
order by tablename;

select count(*) as readers
from core_reader;
```

No insertar saldos, journals, entries o lectores manualmente desde Table Editor.

## 7. Crear el token del lector

```bash
docker run --rm --env-file .env.supabase \
  ogpass-mvp python manage.py provision_reader \
  --name ESP32-001 --amount 1000 --cost 700
```

La salida contiene una sola vez:

```text
READER_TOKEN=valor_privado
```

Copiarlo a `firmware/esp32/src/ogpass_config.h` como `OGPASS_READER_TOKEN`. No guardarlo en Supabase Dashboard, Lovable, Git, capturas ni conversaciones.

## 8. Sincronizar Lovable con el mismo proyecto

Solo después de confirmar que `ynisiarxjpgdxapmoppp` es el proyecto definitivo:

1. En Supabase, pulsar **Connect** o abrir **Project Settings → API Keys**.
2. Para el navegador copiar únicamente:
   - Project URL: `https://ynisiarxjpgdxapmoppp.supabase.co`.
   - Publishable key con formato `sb_publishable_...`.
3. Configurar en Lovable:

```text
VITE_SUPABASE_URL=https://ynisiarxjpgdxapmoppp.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
```

4. Las variables del servidor, sin prefijo `VITE_`, deben ir únicamente en el entorno privado del servidor Lovable:

```text
SUPABASE_URL=https://ynisiarxjpgdxapmoppp.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
```

No cargar una secret key o `service_role` en una variable `VITE_*`. OGPASS no necesita una secret key de Supabase para que Django use PostgreSQL.

## 9. Desplegar Django y verificar el dominio

Supabase no aloja Django. Es necesario desplegar la imagen `ogpass-mvp` en un servidor y crear DNS para `api.ogpass.xyz`.

La prueba final debe responder JSON desde Django:

```bash
curl -i --max-time 10 https://api.ogpass.xyz/health/
```

Solo cuando responda `200`, configurar en el ESP32:

```text
OGPASS_API_BASE=https://api.ogpass.xyz
```

Después se inspecciona el certificado de ese mismo hostname y se instala su CA raíz como `OGPASS_ROOT_CA`. No usar la CA del frontend `ogpass.xyz` por anticipado.

## 10. Checklist final

- [ ] Proyecto definitivo y referencia coinciden en Supabase, Lovable y repositorio.
- [ ] `.env.supabase` existe localmente y no aparece en `git status`.
- [ ] El preflight termina en `OK`.
- [ ] `manage.py migrate` termina sin errores.
- [ ] Table Editor muestra las tablas Django.
- [ ] Data API está desactivada o los roles públicos no tienen acceso al ledger.
- [ ] `provision_reader` generó el token una sola vez.
- [ ] Django está publicado en `https://api.ogpass.xyz`.
- [ ] `/health/` responde HTTP 200.
- [ ] Se instaló la CA raíz correspondiente a `api.ogpass.xyz`.
- [ ] El firmware compila y luego se carga al ESP32.

## Referencias oficiales

- Conexión PostgreSQL y Session pooler: https://supabase.com/docs/guides/database/connecting-to-postgres
- Seguridad de Data API: https://supabase.com/docs/guides/api/securing-your-api
- API keys: https://supabase.com/docs/guides/getting-started/api-keys
- Restablecer contraseña PostgreSQL: https://supabase.com/docs/guides/troubleshooting/how-do-i-reset-my-supabase-database-password-oTs5sB
