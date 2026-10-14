# Base de lanzamiento — transición del 11 de octubre de 2026

`mvp/` es el único runtime de lanzamiento. Django sirve frontend y API del mismo
origen; el frontend de `front_ogpass-sdk-hub` y `sandbox/` no son dependencias de
este runtime. No se importan sus saldos ni se eliminan sus archivos.

```text
mvp/
├── backend/
│   ├── config/                 configuración y URLs efectivas
│   ├── api/                    /api/v1, vistas delgadas
│   ├── apps/identity/          IDs y referencias de tag firmadas
│   ├── apps/credentials/       contrato normalizado y asociación
│   ├── apps/devices/           nodos y eventos autenticados
│   └── tests/                 contratos de lanzamiento
├── config/                    imports compatibles config.settings/asgi/wsgi/urls
├── core/                      ledger/wallet/integraciones existentes y migraciones
├── frontend/{templates,static}/
├── hardware/{core,drivers,protocols,schemas,tests}/
├── prototipos/                únicamente ocho .txt; laboratorio y gates
├── deploy/                    migración separada del runtime
├── evidence/launch-20261011/   nueva evidencia, conserva la histórica
├── scripts/
└── docs/
```

## Dependencias y decisiones de transición

| Dominio | Autoridad actual | Consumidores |
|---|---|---|
| Wallet/ledger | `core/services.py`, `core/models.py`, migraciones 0001–0008 | vistas existentes y API v1 |
| Asociación | `core/cards.py` | APIs existentes, adaptador v1 y normalizador |
| Prerecargas | `core/preloads.py` | vistas y SSE existentes |
| Realtime | `core/realtime.py` | wallet y eventos de dispositivos vía SSE |
| Transporte/integraciones | `core/adapters.py`, `core/transit_credentials.py` | APIs y frontend existentes |
| Identidad/credenciales/dispositivos | `backend/apps/*` | API v1, home, bridge de modelos core |
| Configuración | `backend/config/*` | wrappers `config/*`, manage.py, Docker |
| Frontend | `frontend/templates`, `frontend/static` | Django y collectstatic |
| Hardware | `hardware/*`, ensamblado en `../src/main.cpp` | PlatformIO |

Se conserva el app label `core`. La migración aditiva 0009 crea tablas nuevas y
0010 crea identidades para cuentas existentes sin importar ni cambiar saldos;
no renombra wallet, ledger, journals ni migraciones previas. Las referencias a
`core.*` usadas por comandos, tests y adaptadores continúan funcionando. Extraer
los dominios contables restantes será una transición posterior con pruebas de
migración sobre PostgreSQL; crear paquetes vacíos o duplicar el ledger no la resuelve.

## Identidad y autorización

Cada cuenta obtiene una identidad persistente al acceder al nuevo home/API o al
asociar una credencial. `public_id`, `private_id` y `token_id` son UUID distintos.
El PRIVATE_ID no se serializa, no se imprime ni se graba en tags. Vive en la base
protegida por roles, permisos y backups. No es una clave de pago. TOKEN_ID es una
referencia, no emisión blockchain; WALLET_ID conserva la wallet existente.

La credencial física usa namespace tecnología/protocolo/identificador y una
referencia estable. Un evento no permite reasignar un titular: la asociación
continúa requiriendo lectura fresca, lector activo y controles actuales. Cambiar
tarjeta mantiene wallet; un beacon o UID no autoriza débitos.

`tag_payload.py` prepara/verifica referencias firmadas con Django signing y
caducidad. No existe endpoint público de resolución de perfiles privados ni
escritura de tags. Los identificadores públicos permiten correlación: no se
anuncian por BLE. La vida útil/rotación de un tag físico se decide en prototipo 05.

## Hardware y red

RC522: SS5/SCK18/MISO19/MOSI23/RST27. PN532: SDA21/SCL22, diagnóstico I2C con
timeout, sin uso de RST27. `ReaderManager.beginPrimary()` no inicia módulos
opcionales. PN532/BLE usan tarea separada; red y TLS otra tarea. El loop principal
consume únicamente lecturas disponibles. Fallos de alimentación compartida no
pueden aislarse por software y requieren banco físico.

Eventos v1 son consultas sin cobro. El firmware de esta etapa no arma pagos;
`PAGAR` informa que están deshabilitados. Las APIs de pago previas conservan
confirmación móvil, idempotencia y autoridad del backend. Un futuro firmware de
pago debe recuperar su propósito/referencia persistidos y pasar aceptación.

El envío requiere configuración privada, WiFi/NTP y HTTPS con CA válida. Un
evento en vuelo se persiste en NVS antes del POST; reintentos conservan event_id.
El backend rechaza un mismo UUID con otro contenido o lector. La cola RAM es
acotada y puede perder observaciones al cortar energía; no representa fondos.

SSE existente notifica solo después del commit. Eventos conocidos actualizan la
wallet del titular; los desconocidos son visibles únicamente para staff. No se
añade un segundo sistema de WebSocket. `OGPASS_MODE=developer` permite detalles
solo a staff; cambiar el modo no concede permisos a usuarios normales.

## Configuración y promoción

`OGPASS_ENV=development|test|production`; producción prohíbe DEBUG. `.env` se
carga por el entorno de ejecución/Compose; manage.py no lo ejecuta como shell.
`OGPASS_MODE=product|developer`, producto por defecto. Los cambios de modo
requieren reinicio de los procesos.

BLE es compilación `ble_ibeacon` explícita, experimental. PN532 avanzado, emulación,
NDEF/APDU, Find My, LF y UWB permanecen en fichas .txt. Ninguna compilación o
prueba de software autoriza promover tecnología a producto comercial.

Referencias primarias del laboratorio: [MFRC522](https://github.com/miguelbalboa/rfid),
[BLE del framework fijado](https://github.com/espressif/arduino-esp32/blob/2.0.17/libraries/BLE/src/BLEBeacon.h),
[OpenHaystack, investigación experimental](https://github.com/seemoo-lab/openhaystack).
