# Despliegue de `api.ogpass.xyz`

Esta guía publica el backend Django/ASGI de OGPASS en Render, conectado al PostgreSQL de Supabase. El sitio Lovable `ogpass.xyz` no se reemplaza.

## 1. Crear el servicio en Render

1. Ingresar a Render y elegir **New → Blueprint**.
2. Conectar `BOLIVARES-DIGITALES/OGPASS`.
3. Seleccionar la rama `main` y el archivo `render.yaml`.
4. Confirmar el servicio `ogpass-api`.
5. Cuando Render solicite variables secretas, copiar desde el archivo privado `firmware/esp32/mvp/.env.supabase` únicamente estas claves:
   - `SECRET_KEY`
   - `POSTGRES_HOST`
   - `POSTGRES_USER`
   - `POSTGRES_PASSWORD`
   - `CREDENTIAL_ENCRYPTION_KEY`
   - `CREDENTIAL_HMAC_KEY`
6. No copiar el archivo `.env.supabase` al repositorio ni pegar secretos en `render.yaml`.

El contenedor ejecuta las migraciones antes de levantar Uvicorn y escucha el puerto asignado por Render. El chequeo de salud configurado es `/health/`.

## 2. Probar el dominio temporal

Esperar que el despliegue indique **Live**. En la URL temporal `https://ogpass-api.onrender.com/health/` (o el nombre exacto asignado por Render) debe responder HTTP 200 con JSON similar a:

```json
{"status":"ok","service":"ogpass","payments_connected":false}
```

`payments_connected: false` es correcto mientras Mercado Pago no esté configurado.

## 3. Apuntar solamente el subdominio API

En Render, abrir `ogpass-api → Settings → Custom Domains` y confirmar `api.ogpass.xyz`. Render mostrará el destino DNS exacto.

En el proveedor DNS de `ogpass.xyz`, crear o reemplazar únicamente:

| Tipo | Nombre | Destino | TTL |
|---|---|---|---|
| CNAME | `api` | subdominio `*.onrender.com` indicado por Render | automático o 300 s |

No modificar los registros `@` ni `www`; esos mantienen el frontend de Lovable. Eliminar un registro `AAAA` existente sólo si corresponde específicamente a `api.ogpass.xyz` y entra en conflicto con Render.

Regresar a Render y pulsar **Verify**. Render emitirá y renovará TLS automáticamente.

## 4. Verificación de aceptación

```bash
curl --fail-with-body --silent --show-error \
  --connect-timeout 10 --max-time 90 \
  https://api.ogpass.xyz/health/
```

La aceptación mínima requiere:

- DNS de `api.ogpass.xyz` resolviendo.
- Certificado TLS válido.
- `/health/` con HTTP 200.
- Conexión real a Supabase confirmada por el propio health check.
- Logs de Render sin `DisallowedHost`, errores de migración ni fallos PostgreSQL.

## 5. Conectar el lector

Después de la verificación:

1. Provisionar un lector en la base de datos y obtener su token una sola vez.
2. Configurar en el archivo privado del firmware:
   - `OGPASS_API_BASE=https://api.ogpass.xyz`
   - `OGPASS_READER_TOKEN=<token provisionado>`
   - `OGPASS_ROOT_CA=<CA verificada del certificado vigente>`
3. Compilar, cargar al ESP32 y comprobar `POST /api/reader/heartbeat/`.
4. Acercar una tarjeta OGPASS propia y revisar la lectura en `/ops/`.

La creación del lector y su política económica debe aprobarse antes de emitir el token. Nunca se guarda el token en Git.

## 6. Limitación del plan gratuito

Render Free duerme el servicio después de un periodo sin tráfico. Es suficiente para una prueba controlada si se abre `/health/` antes de encender el lector. Para un lector permanente o una demostración sin espera, cambiar el servicio a una instancia siempre activa.

## 7. Frontend Lovable

El firmware puede consumir `api.ogpass.xyz` directamente. La vista cliente de `ogpass.xyz` usa sesión y CSRF; debe mantener las rutas `/api/`, `/login/`, `/logout/` y `/register/` bajo el mismo origen mediante un proxy, o implementar y probar una política CORS/CSRF explícita antes de configurar `VITE_OGPASS_API_BASE_URL`. No se deben exponer credenciales de Supabase ni tokens del lector al navegador.
