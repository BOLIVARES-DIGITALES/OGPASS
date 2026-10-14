# OGPASS: cierre de base de lanzamiento

Trabajo iniciado el 11 y cerrado el 12 de octubre de 2026. Estado: **base candidata
de software validada**, con aceptación física y de contenedores pendiente.
`firmware/esp32/mvp/` es el único runtime de lanzamiento. No se creó otro MVP,
no se desplegó producción, no se ejecutaron pagos reales ni se flasheó el ESP32.

## 1. Árbol relevante

```text
firmware/esp32/
├── src/main.cpp                         ensamblado y tareas de firmware
├── platformio.ini                       cuatro variantes verificadas
├── scripts/dev-terminals.sh             lanzadores numerados
└── mvp/
    ├── backend/
    │   ├── config/
    │   ├── api/
    │   ├── apps/{identity,credentials,devices}/
    │   └── tests/
    ├── config/                          wrappers compatibles
    ├── core/                            wallet, ledger, servicios y migraciones
    ├── frontend/{templates,static}/
    ├── hardware/
    │   ├── core/
    │   ├── drivers/{rc522,pn532,ble}/
    │   ├── protocols/
    │   ├── schemas/
    │   └── tests/
    ├── prototipos/                      ocho archivos .txt
    ├── deploy/
    ├── scripts/verify_launch_browser.py
    ├── docs/{ARCHITECTURE,API_V1,TESTING_RELEASE}.md
    ├── evidence/launch-20261011/
    ├── Dockerfile
    └── compose.yaml
```

## 2. Archivos creados

Dominios identity, credentials y devices; API v1; pruebas de contratos y
concurrencia; migraciones 0009 y 0010; componentes de frontend; interfaz
OgpassReader, ReaderManager, drivers, transporte HTTPS/NVS, esquema de eventos,
pruebas C++ y fixture de compilación de red. Se añadieron documentación,
verificador de navegador y laboratorio de ocho fichas. El inventario de rutas
está en [changes.json](changes.json).

## 3. Archivos modificados

Firmware, PlatformIO, lanzadores, configuración Django, integración de modelos,
asociación, vistas, middleware, SSE y prueba histórica de navegador. Dockerfile,
Compose, inicialización del rol PostgreSQL, ejemplos de entorno, README e ignores
se actualizaron. También `.vscode/tasks.json` y `.gitignore` de la raíz OGPASS.

Los cambios previos del usuario en README, PlatformIO y main.cpp se tomaron como
base. Las eliminaciones previas de `src/i2c_diag.cpp` y `src/nfc_test.cpp` se
conservaron. No se creó commit ni se hizo push.

## 4. Archivos movidos

`mvp/templates/` → `mvp/frontend/templates/` y `mvp/static/` →
`mvp/frontend/static/`. Las implementaciones de settings/urls/asgi/wsgi se
trasladaron a `backend/config/`; `config/` conserva imports compatibles.
Wallet, ledger e integraciones permanecen en `core/` para preservar migraciones
y consumidores; su extracción posterior está documentada, sin duplicar lógica.

## 5. Archivos ignorados y configuración privada

Se mantienen fuera del repositorio `.env`, `src/ogpass_config.h`, entornos Python,
DBs locales, caches, staticfiles, node_modules y binarios de compilación. Se
preservó la evidencia anterior. La revisión heurística no identificó credenciales
reales versionadas; los candidatos de plantillas son marcadores de ejemplo.
Alcance y límites en [secret-audit.json](secret-audit.json).

## 6. Drivers disponibles

| Driver | Rol | Capacidades implementadas |
|---|---|---|
| RC522 | PRIMARY | IDENTIFY, READ (UID/metadatos), HEALTH |
| PN532 | OPTIONAL | HEALTH: diagnóstico de dirección I2C |
| BLE | RADIO, opt-in | BEACON, HEALTH |

La interfaz incluye begin/health/detect/read/write/emulate/capabilities/reset.
WRITE y EMULATE devuelven no soportado. No se anuncian como disponibles todas
las capacidades teóricas del chip.

## 7. Protocolos disponibles

ISO14443A para identificación RC522; contrato normalizado versionado; HTTP API
con autenticación, HTTPS del dispositivo con CA y SSE del backend. iBeacon se
compila como laboratorio. Protocolos no reconocidos generan
`UNKNOWN_TECHNOLOGY` sin asociación automática ni movimientos contables.
No se implementaron lectura de saldo externo, clonación, APDU, NDEF o LF.

## 8. Estado RC522

Arranca primero y trabaja en el loop principal. Pines SS5/SCK18/MISO19/MOSI23/
RST27. El driver no conoce wallet, identidad ni backend. Hay sondeo de salud y
lectura UID/SAK/ATQA. Compilación verificada; falta aceptación con tarjetas reales.

## 9. Estado PN532

SDA21/SCL22, timeout de bus y estados CONNECTED/OFFLINE/ERROR/DISABLED.
La operación opcional ocurre fuera del loop principal. La prueba de aislamiento
demuestra 1.000 polls del primario sin invocar I/O opcional. La detección I2C no
certifica lectura NFC. Fallos eléctricos compartidos requieren banco físico.

## 10. Estado BLE

Driver opt-in `ble_ibeacon`, UUID fijo de laboratorio, payload iBeacon probado
en C++ y compilación exitosa. No expone PRIVATE_ID ni autoriza pagos. Quedan
pendientes RF, recepción, calibración, consumo y coexistencia WiFi/BLE. La imagen
BLE ocupa aproximadamente 88,3% de la partición; red activa y BLE combinados
requieren medir tamaño y memoria antes de aceptación.

## 11. Estado backend

Identidad persistente con PUBLIC_ID/PRIVATE_ID/WALLET_ID/TOKEN_ID; PRIVATE_ID no
se serializa. TOKEN_ID es una referencia, no emisión blockchain. Las referencias
de tag se firman y verifican, sin escribir tarjetas. API `/api/v1/` para perfil,
wallet, credenciales, dispositivos, registro, desactivación, escaneo, asociación,
eventos y salud. Autorización por sesión/CSRF o token del lector según operación.

Los eventos tienen UUID, idempotencia, auditoría y normalización; reintentos no
duplican lecturas. Las observaciones no debitan wallet. Se conserva confirmación
móvil en las APIs de pago existentes. El firmware de esta etapa mantiene
`PAGAR` deshabilitado. Ledger, reconciliación y restricciones PostgreSQL pasaron
las pruebas. Las migraciones se probaron en DBs temporales, sin migrar la DB
personal del usuario ni importar fondos.

Compose espera la migración con rol propietario antes del runtime de aplicación.
El nombre de DB y la conexión del migrador quedan explícitos. Docker no está
instalado en este entorno: build y arranque de contenedores **no verificados**.

## 12. Estado frontend

Django sirve interfaz y API desde el mismo origen. Home con identidad pública,
wallet, credenciales, dispositivos y actividad; navegación Inicio/OGPASS/Menú.
Developer Mode requiere tanto `OGPASS_MODE=developer` como cuenta staff. La
vista producto oculta metadatos técnicos. Se conserva la asociación existente y
se añaden diagnóstico y desactivación autorizada de dispositivos.

Navegador verificado en 375/390/430/768/1440 px sin desbordamiento ni errores JS.
SSE se probó con ASGI real, SQLite temporal y PostgreSQL temporal con
LISTEN/NOTIFY. Los lectores fueron simulados por HTTP: esto no prueba RF.

## 13. Pruebas ejecutadas

| Validación | Resultado | Evidencia |
|---|---|---|
| Baseline backend | 61 pruebas, 5 omitidas en SQLite | baseline-sqlite.txt |
| Backend final SQLite | 76 pruebas, 7 omitidas por requerir PostgreSQL | [final-sqlite.txt](final-sqlite.txt) |
| Backend final PostgreSQL + navegador histórico | **77 pruebas, todas pasan** | [final-postgres.txt](final-postgres.txt) |
| Rol runtime restringido | posting simulado y rechazo de truncado/drop/manipulación | [runtime-role.txt](runtime-role.txt) |
| UI v1 + SSE SQLite | PASS, cinco tamaños, evento observado en 849 ms | [browser.json](browser.json) |
| UI v1 + SSE PostgreSQL | PASS, cinco tamaños, evento observado en 148 ms | [browser.json](postgres-browser/browser.json) |
| Hardware C++ nativo | aislamiento, fallback, escritura no soportada, bytes iBeacon | [hardware-native.txt](hardware-native.txt) |
| Firmware | esp32dev, esp32developer, ble_ibeacon, network_compile_test: SUCCESS | [firmware-all.txt](firmware-all.txt) |
| Django/check/migraciones/static | sin errores ni migraciones pendientes de generar; assets presentes | [config-checks.txt](config-checks.txt) |
| Higiene | diff --check, sintaxis shell y ocho .txt: PASS | revisión local |

Los tiempos de SSE son observaciones de una ejecución local, no un SLA.
`network_compile_test` usa credenciales ficticias y CA inválida: **no flashear**.
La prueba histórica utiliza proveedor de pagos simulado; no acredita pagos reales.
Se conserva evidencia de intentos intermedios fallidos. El fallo de navegador
se corrigió usando StaticLiveServerTestCase para servir fuentes actuales en vez
de staticfiles antiguos; las verificaciones de errores JS se mantienen.

## 14. Riesgos y límites

- Falta banco físico RC522/PN532/BLE y red con CA válida, desconexión y reinicio.
- Cola RAM acotada: observaciones pendientes pueden perderse al cortar energía.
  El evento en vuelo se persiste en NVS y conserva su UUID al reintentar.
- Falta build/arranque Docker, aceptación TLS y ensayo de restauración de backup.
- La configuración privada incompleta permite compilar offline; eso no demuestra
  conectividad ni lectura real. Completarla localmente para la aceptación.
- UID/beacon no prueban propiedad ni autorizan débito; los controles de asociación
  existentes siguen siendo necesarios.
- La separación de dominios contables es progresiva; `core/` sigue siendo su
  autoridad. No hay certificación comercial ni OTA implementada en este sprint.

## 15. Tecnologías todavía en prototipos

NFC multiprotocolo, PN532 avanzado y emulación, BLE/iBeacon, investigación Find
My/OpenHaystack, tag firmado físico, multirradio y gate de producto. Las ocho
fichas incluyen objetivo, hardware, protocolo, capacidades, pruebas, resultados,
riesgos y criterios de promoción. Estado: **ITERATE**.

## 16. Tecnologías promovidas a producto

**Ninguna nueva tecnología física promovida a producto comercial.** RC522 se
mantiene como lector principal de la base. Identidad, normalización, API y UI se
integran en el software candidato; la compilación no sustituye el gate físico.

## 17. Siguiente acción y checklist de aceptación

Seguir [TESTING_RELEASE.md](../../docs/TESTING_RELEASE.md). Desde
`firmware/esp32`, `bash scripts/dev-terminals.sh backend` migra exclusivamente
`db.nfc-dev.sqlite3` y abre el backend de desarrollo; en otra terminal,
`bash scripts/dev-terminals.sh frontend` abre la interfaz.

- [ ] Crear/iniciar sesión con cuenta local y revisar identidad, saldo y permisos.
- [ ] Completar configuración privada WiFi/token/CA hacia el backend HTTPS de prueba.
- [ ] Identificar puerto con `bash scripts/dev-terminals.sh ports`.
- [ ] Cargar `esp32dev` y verificar tarjetas propias sin generar cargos.
- [ ] Desconectar PN532 y comprobar que RC522, red y backend siguen operativos.
- [ ] Probar pérdida de red, reintento con mismo UUID y reinicio con evento NVS.
- [ ] Medir BLE y coexistencia antes de habilitarlo en una variante candidata.
- [ ] Construir y arrancar Compose con credenciales y base exclusivas de pruebas.
- [ ] Registrar evidencia física, consumo y estabilidad; evaluar gate 07.

Los servicios y bases temporales utilizados por las pruebas se cerraron al
terminar. El código queda disponible en el workspace para revisión.
