# OGPASS MVP

Django 5.2 + PostgreSQL + web móvil del mismo origen + ESP32/PN532. Código creado en `firmware/esp32/mvp` porque este es el workspace con permiso de escritura. `backend/` estaba vacío; el prototipo `sandbox/` se conserva y no se migra automáticamente: sus JSON no son evidencia de fondos reales.

## Estado de entrega

Consultar [evidence/DELIVERY.md](evidence/DELIVERY.md) para verificaciones y bloqueos reales. No existe un checkout simulado activable en producción. Sin credenciales verificables las recargas permanecen deshabilitadas.

## Flujo

1. Usuario crea cuenta e inicia sesión en `/`.
2. En «Mi tarjeta» introduce el ID de nueve dígitos y pulsa Asociar tarjeta. En `/ops/`, el administrador selecciona la solicitud y confirma su vinculación con una lectura reciente del lector. El número impreso no se convierte a UID ni vincula por sí solo una tarjeta física.
3. Crea recarga de $500–$200.000 CLP y paga en checkout alojado de Mercado Pago Chile. También puede pagarla OGPASS con sus fondos reales para ese usuario.
4. Backend valida firma de webhook y consulta `GET /v1/payments/{id}`. Solo acredita pagos aprobados **live**, en CLP, del collector configurado y por el importe/referencia exactos. La URL de retorno del checkout no acredita.
5. Al acercar el tag al PN532, el modo normal consulta el saldo OGPASS sin crear un pago. Para pagar, el operador envía `PAGAR` por el monitor serie y acerca el tag en los siguientes 30 segundos. Precio y costo provienen del backend; el firmware no puede elegirlos.
6. Móvil muestra una solicitud válida durante 90 segundos. Usuario confirma; backend bloquea su wallet, verifica saldo y registra el débito y sus contrapartidas atómicamente.
7. Lector consulta el resultado. Un HTTP 200 con `pending` **no** es aprobación. NVS conserva referencia y UID para recuperar un timeout o reinicio.
8. Administrador consulta `/ops/`, concilia pagos por ID y reversa únicamente servicios no prestados, con motivo. Los movimientos originales no se borran.

El UID puede clonarse: se usa como referencia, y **cada débito requiere la sesión móvil del titular**. Las pantallas de alta explican esa condición. El lector no opera sin conexión al backend.

## Arquitectura y contabilidad

- CLP entero, débitos positivos y créditos negativos; saldo usuario = negativo de la suma de su cuenta `wallet:<id>`.
- Recarga: débito fondos por cobrar al proveedor netos + gasto de comisión / crédito pasivo usuario por importe bruto.
- Operación: débito pasivo usuario / crédito ingresos; débito costo de servicio / crédito proveedor por pagar.
- Reverso completo: asientos opuestos vinculados al original. Solo para servicio no prestado: revierte también costo. Una devolución de un servicio ya prestado necesita un asiento específico y no debe usar este botón.
- Margen operación = precio − costo. Resultado acumulado = ingresos − costos − comisiones de recarga. No incluye gastos fijos, impuestos ni costos no registrados. Configuración inicial propuesta: precio 1000, costo 700; confirmar costo contractual antes de habilitar un lector real. No se garantiza rentabilidad por fijar un precio.
- Comisión real proviene de `fee_details`; fracciones se redondean hacia arriba al CLP para no subestimar costos. Conciliar cualquier diferencia de redondeo frente a liquidaciones.
- Fondos por cobrar a Mercado Pago no son saldo bancario liquidado. Conciliación de liquidaciones bancarias es manual en este MVP; no existe feed bancario conectado.
- Reembolsos, parciales y contracargos detectados congelan la wallet y generan alerta `review_required`. No se automatiza un retiro de fondos ya gastados. La resolución contable de disputas requiere intervención operativa; no hay botón de reembolso externo.
- PostgreSQL exige balance cero por journal al commit y prohíbe UPDATE/DELETE de asientos, journals y auditoría. El usuario de aplicación no debe ser superusuario. Superusuarios/propietarios de DB siguen pudiendo alterar el esquema; backups externos son necesarios.
- `select_for_update` serializa cobros/recargas/reversos por wallet. Idempotencia global de toques y recargas, referencia única de pago y reverso único por journal.
- SQLite es solo desarrollo; producción exige PostgreSQL. Adaptadores separados en `core/adapters.py`.
- Web con sesiones Django, CSRF, autorización por propietario, TLS, cabeceras de seguridad y límites de solicitudes compartidos en DB.
- Usuarios nuevos pueden registrarse; no hay recuperación por correo hasta conectar SMTP. Admin puede gestionar credenciales mediante Django admin.

## Desarrollo local

```bash
cd /home/uniquedev/Escritorio/OGPASS/firmware/esp32/mvp
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
DEBUG=1 .venv/bin/python manage.py migrate
DEBUG=1 .venv/bin/python manage.py createsuperuser
DEBUG=1 .venv/bin/python -m uvicorn config.asgi:application --host 127.0.0.1 --port 8000
```

Abrir `http://127.0.0.1:8000`. Web y API usan Django; no hay build Node ni CORS. HTTP local no sirve para el firmware: el lector exige HTTPS con CA válida. Para la prueba física usar el dominio configurado.

```bash
DEBUG=1 .venv/bin/python manage.py test core --verbosity 2
# Con POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER y POSTGRES_PASSWORD exportados:
DEBUG=1 .venv/bin/python manage.py test core --verbosity 2
```

La suite PostgreSQL incluye carreras de dos cobros y rechazo de alteraciones/desbalance contable. La suite SQLite omite esos casos explícitamente.

## Despliegue hoy: preparación en servidor

Requisitos: Linux con Docker Engine + Compose, puertos 80/443 públicos, dominio A hacia la IP del servidor (AAAA solo si IPv6 funciona), acceso SSH. Copiar esta carpeta al servidor, por ejemplo `/opt/ogpass/mvp`. No copiar `db.sqlite3`, claves Testnet de prueba ni `.env` de otra instalación.

### Dominio `ogpass.xyz` en Hostinger

El dominio actualmente redirige a `bolivaresdigitales.online`; no cambies sus registros DNS hasta tener lista la IP pública del servidor y acordar el cambio de tráfico. Este despliegue con Docker Compose requiere un VPS Hostinger con Docker y acceso SSH; el hosting web compartido no ejecuta esta arquitectura. Para el corte, apunta el registro A de `@` a la IPv4 del VPS, configura `www` como CNAME a `ogpass.xyz` si se desea, y elimina registros AAAA solo si el VPS no ofrece IPv6 funcional. Permite tráfico entrante TCP 80/443 y UDP 443 para Caddy. Completa el `.env` local del servidor antes de ejecutar `preflight.py`; no copies el archivo local de desarrollo con marcadores.

```bash
cd /opt/ogpass/mvp
cp .env.example .env
chmod 600 .env
# Editar .env con dominio, claves aleatorias y credenciales del proveedor.
# Generar valores distintos para SECRET_KEY, POSTGRES_PASSWORD y POSTGRES_ADMIN_PASSWORD:
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
docker compose build backend migrate
docker compose up -d db
docker compose run --rm migrate python deploy/preflight.py
docker compose run --rm migrate python manage.py check --deploy
docker compose run --rm migrate
docker compose run --rm backend python manage.py createsuperuser
docker compose run --rm backend python manage.py provision_reader --name ESP32-001 --amount 1000 --cost 700
```

El último comando muestra el token una sola vez. Guardarlo en `src/ogpass_config.h`; ejecutarlo otra vez rota el token e invalida el anterior. Ajustar precio/costo a la operación comercial confirmada. Compose separa el rol migrador `ogpass_owner` del rol de aplicación `ogpass`, sin privilegios de superusuario, creación de roles, tablas ni TRUNCATE. El script inicial se ejecuta solo en un volumen nuevo.

**Terminal 1 — backend (en servidor)**

```bash
cd /opt/ogpass/mvp
docker compose up -d backend
docker compose logs -f backend
```

**Terminal 2 — web y HTTPS (en servidor)**

```bash
cd /opt/ogpass/mvp
docker compose up -d web
docker compose logs -f web
```

Caddy obtiene/renueva el certificado del dominio automáticamente. Uvicorn ASGI y PostgreSQL no exponen puertos al host. Ambos servicios reinician automáticamente; cerrar terminales no detiene los contenedores. La web está renderizada por Django y Caddy atiende el dominio.

**Terminal 3 — lector (en el PC conectado por USB)**

```bash
cd /home/uniquedev/Escritorio/OGPASS/firmware/esp32
cp src/ogpass_config.example.h src/ogpass_config.h
# Editar Wi-Fi, https://dominio, token del lector y CA raíz PEM válida.
/home/uniquedev/Escritorio/OGPASS/.venv/bin/pio device list
/home/uniquedev/Escritorio/OGPASS/.venv/bin/pio run
# Sustituir /dev/ttyUSB0 si device list informa otro puerto.
/home/uniquedev/Escritorio/OGPASS/.venv/bin/pio run --target upload --upload-port /dev/ttyUSB0
/home/uniquedev/Escritorio/OGPASS/.venv/bin/pio device monitor --port /dev/ttyUSB0 --baud 115200
```

PN532 en modo I2C: SDA GPIO21, SCL GPIO22, GND común, alimentación conforme al módulo y lógica de 3,3 V compatible con ESP32. Firmware sincroniza NTP antes de TLS; el certificado CA debe validar la cadena actual del dominio. No usa `setInsecure`. Sin `ogpass_config.h` compila con conexión deshabilitada.

## Activar Mercado Pago Chile

Cargar en `.env`: `MP_ACCESS_TOKEN` de producción, `MP_WEBHOOK_SECRET` del webhook y `MP_COLLECTOR_ID` del vendedor. Configurar notificaciones **payment** en `https://DOMINIO/api/payments/webhook/`. Usar HTTPS y la aplicación del mismo vendedor. La firma usa `data.id`, `x-request-id`, timestamp y HMAC SHA256 según la documentación oficial.

```bash
docker compose up -d --force-recreate backend
```

Prueba de aceptación real (pendiente hasta disponer de las credenciales): recarga de $5.000 CLP (o al menos el precio del lector) con un medio real de OGPASS, esperar estado `credited`, comparar ID y comisión con el panel de Mercado Pago, consultar saldo con el tag, enviar `PAGAR` por el monitor serie, volver a tocar, confirmar en móvil y verificar saldo, asientos, margen y panel del lector. El pago real puede tener comisión y no lo sustituye la prueba automatizada con respuestas del proveedor controladas.

Si un webhook se pierde, usar `/ops/` → conciliar pago con ID del proveedor; el backend vuelve a consultar su estado. Si hubo dos pagos diferentes de una misma recarga, el segundo no se acredita automáticamente: reconciliar y resolver devolución con el proveedor.

## Stellar y transporte

```bash
# Dentro del servidor; guardar secretos fuera del código y con persistencia segura.
docker compose exec backend python manage.py stellar_account USUARIO --secret-file /home/app/testnet-USUARIO.key
# Para cuenta ya creada y clave en custodia propia:
docker compose exec backend python manage.py stellar_account USUARIO --address DIRECCION_PUBLICA_TESTNET
# Mainnet: asociación pública de solo lectura, sin fondeo ni firmas.
docker compose exec backend python manage.py stellar_account USUARIO --network mainnet --address DIRECCION_PUBLICA_MAINNET
```

El contenedor es efímero: exportar inmediatamente la clave generada a custodia segura o usar `--address` con una cuenta creada en custodia propia. Nunca guardar claves en la base de datos ni repositorio. Testnet usa Friendbot y Horizon Testnet; Mainnet consulta exclusivamente Horizon público. Cada red tiene un registro separado y ninguna modifica CLP. XLM es el activo verificable inicial; emisión de un activo OGPASS/trustlines no está implementada. Los reinicios de Testnet pueden eliminar cuentas: la UI muestra `unfunded` y el comando permite fondear de nuevo.

Transporte: adaptador explícito `not_connected`, saldo `null`; hace falta identificar proveedor, documentación, endpoint y autorización. No intenta extraer ni modificar saldos de tarjetas ajenas.

## Operación, copias y rollback

```bash
cd /opt/ogpass/mvp
docker compose exec backend python manage.py reconcile
docker compose exec backend python manage.py clearsessions
docker compose exec backend python manage.py prune_rate_buckets
# Guardar backups fuera del servidor y probar restauración antes de producción.
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > ogpass-backup.dump
```

Programar copia diaria cifrada y retención fuera del host. Restaurar en una DB nueva, verificar `reconcile` y migraciones antes de cambiar tráfico. En rollback de código, conservar la DB y volver a la imagen anterior compatible; no borrar volúmenes ni ejecutar migraciones inversas de ledger para recuperar una versión. Nunca importar los saldos JSON del sandbox como fondos reales.

## Referencias oficiales consultadas

- [Mercado Pago: notificaciones](https://www.mercadopago.cl/developers/en/docs/checkout-pro-preferences/payment-notifications)
- [Django: checklist de despliegue](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [Stellar: creación de cuentas](https://developers.stellar.org/docs/build/guides/transactions/create-account)
- [Stellar: redes y reinicios de Testnet](https://developers.stellar.org/docs/networks)

## Verificación visual reproducible

Instalar dependencias opcionales solo para pruebas:

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
# Exportar conexión a PostgreSQL de pruebas; nunca usar credenciales de producción.
DEBUG=1 .venv/bin/python manage.py test core.browser_tests --verbosity 2
```

La prueba abre Chromium a 390 px, recarga mediante un proveedor controlado, entrega webhook firmado con respuesta canónica controlada, toca mediante HTTP, confirma desde la web y comprueba el panel. Las capturas llevan marca de prueba; no demuestran un cobro real ni una lectura física.


## Actualización 25/09: tarjetas, prerecargas y eventos

### Tarjeta y consulta sin cobro

La vista privada conserva Fondos → Movimientos → Recargas. Desde Fondos, «Asociar mi tarjeta» abre el asistente:

1. Número impreso: por ejemplo `114309782`. Para precargar únicamente el formulario de la sesión actual: `/?card_number=114309782#my-card`.
2. Acercar la tarjeta propia al PN532 con el firmware actualizado. Una tarjeta desconocida genera un código de 10 caracteres, solo visible en la respuesta autenticada del lector/monitor serie.
3. Introducir ese código y confirmar el consentimiento en la web. La asociación es a la cuenta autenticada; no se acepta introducir un UID libre para apropiarse de una credencial.
4. Retirar y volver a acercar la tarjeta. Se devuelve el saldo disponible del ledger OGPASS, su fuente y fecha de consulta; también aparece en la web. Si no hay fondos confirmados, muestra $0. No se fabrica saldo de transporte.

Las lecturas normales usan `POST /api/reader/scans/` con `{uid, key, purpose:"balance"}` y consulta posterior `GET /api/reader/scans/<key>/`. El mismo key recupera la lectura y consulta el saldo actual. No genera Operation ni Journal. `purpose:"payment"` es explícito y requiere confirmación móvil. El endpoint antiguo `/api/reader/touch/` se conserva para compatibilidad y sigue creando solicitudes de pago; actualizar el firmware para usar consulta por defecto.

En el monitor: `SALDO` vuelve a modo consulta, `PAGAR` habilita solo la siguiente lectura durante 30 segundos. La referencia, UID y propósito se guardan juntos en NVS antes de enviar. Firmware sin Wi-Fi/token/CA sigue sin conectarse.

«Reemplazar» dentro del asistente asocia la tarjeta nueva, desactiva la anterior y conserva el mismo wallet. Fondos y prerecargas no cambian. No es una copia física ni una transferencia de saldo del emisor bip!. Los códigos de asociación caducan; los fondos no caducan por esa razón.

### Prerecargas respaldadas

- Administrador: `/ops/` → «Asignar prerecargas OGPASS». Seleccionar usuario e importe. Solo puede reservar fondos disponibles de su propia cuenta administradora, acreditados previamente; no hay creación arbitraria de dinero.
- Reserva: débito del pasivo de la wallet de origen / crédito del pasivo `preload:<id>`. El importe deja de estar disponible al administrador.
- Usuario: Recargas → «Prerecargas por activar» → «Activar». Débito del pasivo reservado / crédito de su wallet; una única vez aunque haya doble clic o solicitudes concurrentes.
- Sin fecha de vencimiento. Siguen pendientes al cambiar de tarjeta. Una vez activadas, los fondos siguen en la cuenta hasta su uso. No son un saldo infinito ni una carga bip!.
- El emisor puede cancelar una prerecarga pendiente y recuperar su reserva. Una activada no puede cancelarse por esta vía. Cuentas receptoras u origen bloqueadas impiden activar.
- Se rechaza asignar sin respaldo; cuentas de prueba y fixtures viven únicamente en bases aisladas de test. No se cargaron fondos simulados a la cuenta local del usuario.

### Actualizaciones en vivo

Producción usa Uvicorn/ASGI, Server-Sent Events y PostgreSQL LISTEN/NOTIFY. Cada movimiento persiste un `WalletEvent` dentro de su transacción: la notificación solo se entrega al commit. Hay un listener PostgreSQL por worker y colas por sesión para agrupar avisos. El navegador vuelve a leer el estado autorizado, evitando reutilizar un saldo incluido en una notificación antigua.

`/api/events/` requiere sesión y solo avisa de la propia wallet. `/api/ops/events/` y `/api/ops/state/` requieren staff; actualizan los saldos, resultados y tabla de prerecargas administrativa. Las conexiones se renuevan para revalidar sesión, y cada reconexión consulta el estado actual. Si falla SSE, la UI indica reconexión y usa consultas cada 5 segundos. SQLite local usa comprobación de eventos cada 500 ms en el servidor; la ruta PostgreSQL usa notificaciones.

Las operaciones vencen según backend; la interfaz solicita actualización al alcanzar su fecha límite. Los saldos externos tienen otra garantía: Stellar se consulta cada 60 segundos y transporte continúa sin conexión. No se afirma tiempo real para una fuente que no entrega datos.

La prueba `evidence/verify_realtime.py` ejecuta Uvicorn, PostgreSQL aislado y Chromium, registra latencias y verifica asignación, activación, consulta sin débito, reemplazo y reconexión. Ver [resultados](evidence/realtime-flow.json). Las mediciones locales no son un SLA ni una prueba de carga en el dominio.

### Copia/escritura NFC: pendiente

No se ha habilitado escritura, clonación de UID ni copia de datos/saldo bip!. Para implementar una credencial **OGPASS propia** grabable, faltan confirmación de contenido, modelo exacto del tag de destino y acceso al lector físico. Una credencial de aplicación en memoria de usuario de un tag compatible no equivale a copiar el UID de fábrica ni el monedero del transporte.

Las cargas remotas bip! requieren los mecanismos del operador; [bip! describe los canales de activación](https://www.tarjetabip.cl/tipos-de-carga.php). Esa integración no está conectada a OGPASS. La documentación [NXP sobre tags NFC Type 2](https://www.nxp.com/docs/en/data-sheet/NTAG210_212.pdf) distingue memoria de usuario del UID programado de fábrica.


### Actualización: asociación simplificada y lector en `/ops/`

La UI vigente usa un solo campo de nueve dígitos. Guarda una solicitud pendiente, sin crear un tag ficticio. El administrador verifica el titular y el número impreso contra la tarjeta presente, selecciona la solicitud y confirma la última lectura explícita del lector. Se rechazan lecturas expiradas, sustituidas por otra más reciente o de lectores desconectados. Requiere migración `0007`.

El panel del lector consulta su estado cada 2 segundos; considera desconectado un dispositivo sin señal durante 45 segundos. Muestra UID leído, número asociado y titular solo a administradores. El CTA de copia abre un diálogo que informa que la escritura no está habilitada: no envía comandos ni muestra un éxito ficticio. El firmware sigue siendo de lectura. Falta modelo de tarjeta destino y contenido propio a grabar.

El protocolo previo con código temporal se conserva por compatibilidad; ya no se solicita ese código en el formulario del usuario. La UI simplificada agrega tarjetas a la misma cuenta. La desactivación de una tarjeta anterior puede gestionarse en Django admin; el endpoint previo mantiene la operación de reemplazo atómico.


### Consulta de saldo bip! por número (estado verificado)

Guardar nueve dígitos muestra inmediatamente la tarjeta y su sección de transporte, incluso si el NFC aún no está vinculado. `/api/transport/` exige sesión y solo incluye los números guardados o vinculados a esa cuenta. Comprueba la disponibilidad del portal público cada cinco minutos por proceso, sin enviar números ni datos de cuenta. Los estados son `verification_required`, `unavailable`, `integration_required` y `no_card`; ninguno representa un saldo obtenido.

El enlace oficial `https://www.tarjetabip.cl/testPOCAE.php` dirige a `http://pocae.tstgo.cl/PortalCAE-WAR-MODULE/`. Durante la comprobación respondió por HTTP y mostró verificación visual CAPTCHA; HTTPS en el destino rechazó conexión. No se elude esa verificación ni se transforma una consulta de disponibilidad en un saldo. La interfaz permite copiar el número y abrir el portal oficial para realizar la consulta allí. Ese resultado no se importa automáticamente a OGPASS.

Para mostrar importes automáticamente falta una API del operador/proveedor autorizada para consulta de saldo, con documentación, credenciales y fecha efectiva del dato. El saldo bip! debe conservar fuente y antigüedad y permanecer separado del ledger OGPASS. No se conoce el saldo de la tarjeta 114309782 con esta entrega. Evidencia: `evidence/bip-source-check.json`; pruebas de estados y aislamiento: `evidence/tests-transport.txt`.


### Monitor NFC y demostración de copia

Junto a «Copiar número», «Monitor NFC / Copiar a llavero» abre un diálogo accesible con el número guardado, estado del lector y última lectura de esa tarjeta disponible para la cuenta. Consulta `/api/state/` cada dos segundos solo mientras está abierto; cerrar o abandonar la página detiene el monitor. Los errores de conexión no se muestran como lector en línea.

La sección DEMOSTRACIÓN se inicia explícitamente y usa una referencia ficticia. No transmite órdenes al lector ni cambia tags, saldo o datos de cuenta. «Escribir en llavero» permanece deshabilitado: el firmware no extrae memoria ni metadatos completos, no escribe y no verifica físicamente una copia. El cierre cancela las animaciones pendientes. Para implementar escritura de datos propios OGPASS se requiere identificar el tag de destino y especificar el contenido permitido; el número guardado no representa un volcado NFC.
