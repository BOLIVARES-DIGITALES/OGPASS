# Checklist de pruebas OGPASS

Preparado el 2026-10-02 contra el checkout local `0fc7f2b` (`main`).
Revisión de documentación y cobertura; las pruebas siguientes están **pendientes de ejecución**.
No se hizo fetch/pull: la revisión corresponde al repositorio local, no verifica novedades remotas.

Usar `[x]` solo con resultado comprobado. Registrar por caso: fecha, commit, entorno,
resultado (PASS/FAIL/BLOQUEADO/OMITIDO), evidencia sin secretos y observaciones.
Las evidencias de ejecuciones anteriores no validan automáticamente esta ronda.

## 1. Preparación

- [ ] Registrar `git status --short --branch` y `git rev-parse HEAD`.
- [ ] Usar base de pruebas aislada, dos usuarios y un administrador; no usar producción.
- [ ] Confirmar entorno Python y dependencias de `requirements.lock`.
- [ ] Configurar PostgreSQL exclusivo de pruebas para concurrencia y protecciones contables.
- [ ] Mantener `.env`, tokens, claves y `src/ogpass_config.h` fuera de Git y de las evidencias.
- [ ] Usar respuestas controladas del proveedor y fondos de fixtures únicamente en bases de pruebas.
- [ ] Para hardware: ESP32, PN532 en I2C, tarjeta propia, USB, Wi-Fi y endpoint de pruebas HTTPS con CA válida.

## 2. Verificación automática

Desde la raíz del workspace:

```bash
pio run
```

Si `pio` no está en PATH, el README documenta el ejecutable
`/home/uniquedev/Escritorio/OGPASS/.venv/bin/pio`.

Desde `mvp/`, usando el Python del proyecto (por ejemplo `.venv/bin/python`):

```bash
# SQLite: omitir POSTGRES_HOST del entorno de este proceso.
env -u POSTGRES_HOST DEBUG=1 .venv/bin/python manage.py test core --verbosity 2

# PostgreSQL: exportar POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER y
# POSTGRES_PASSWORD de una instancia EXCLUSIVA de pruebas antes de ejecutar.
DEBUG=1 .venv/bin/python manage.py test core --verbosity 2

# Navegador: requiere requirements-dev.txt y Chromium de Playwright.
DEBUG=1 .venv/bin/python manage.py test core.browser_tests --verbosity 2
```

- [ ] Firmware compila sin errores. Registrar si usó configuración privada o conexión deshabilitada.
- [ ] Suite SQLite pasa; registrar cantidad de pruebas y omisiones explícitas.
- [ ] Suite PostgreSQL pasa, incluidos los cinco casos de `PostgresConcurrencyTests`.
- [ ] Chromium pasa en PostgreSQL: móvil, confirmación y panel administrativo; sin errores JS ni HTTP 500.
- [ ] Ejecutar `evidence/verify_realtime.py` solo tras revisar sus requisitos: socket `/tmp/ogpass-postgres`, rol local `uniquedev`, permiso para crear/eliminar su base temporal y puerto 8011 disponible. El script sobrescribe evidencias; conservar los resultados anteriores si se necesitan.
- [ ] Verificar también permisos del rol de aplicación: sin superusuario ni capacidad de alterar tablas, desactivar protecciones o hacer TRUNCATE. Las pruebas con un rol privilegiado no certifican el rol de producción.

## 3. Cuenta, tarjeta y permisos

- [ ] Registro e inicio/cierre de sesión funcionan; cuenta nueva con saldo OGPASS cero.
- [ ] Número de tarjeta: exactamente nueve dígitos; entradas inválidas rechazadas.
- [ ] Guardar número crea solicitud pendiente, sin inventar UID ni asociación física.
- [ ] Administrador verifica titular y número impreso y vincula una lectura específica reciente desde `/ops/`.
- [ ] Lectura expirada, sustituida o lector desconectado: vinculación rechazada.
- [ ] Reintentar vinculación no duplica ni permite apropiarse de tarjeta ajena.
- [ ] Usuario A no consulta ni confirma operaciones, tarjetas o prerecargas de B.
- [ ] Sesión, CSRF y permisos staff se exigen; token de lector ausente/incorrecto se rechaza.
- [ ] Nueva tarjeta de la misma cuenta conserva fondos y prerecargas. La UI agrega tarjetas; desactivar la anterior desde admin si corresponde. El endpoint de reemplazo conserva su comportamiento atómico.

## 4. ESP32 y consulta sin cobro

- [ ] PN532 detectado; SDA GPIO21, SCL GPIO22, GND común y alimentación adecuada al módulo.
- [ ] Wi-Fi, NTP y TLS funcionan con CA válida; una CA inválida impide conectar.
- [ ] Heartbeat visible en `/ops/`; tras 45 segundos sin señal aparece desconectado.
- [ ] Lectura normal y comando `SALDO` muestran saldo OGPASS, fuente y fecha.
- [ ] Consultas repetidas no crean `Operation` ni `Journal` y no alteran el saldo.
- [ ] Reintento de la misma referencia devuelve saldo actual sin duplicar efectos.
- [ ] Tarjeta desconocida, desactivada o wallet bloqueada no permiten gasto ni exponen saldo indebidamente.
- [ ] Cortar red y reiniciar durante una solicitud conserva referencia, UID y propósito en NVS; al reconectar no duplica cargos.
- [ ] Sin conexión al backend, el lector no aprueba operaciones.

## 5. Pagos y ledger en entorno aislado

- [ ] `PAGAR` habilita la siguiente lectura durante 30 segundos; vencido ese plazo no inicia pago.
- [ ] Lectura de pago genera `pending`, sin débito ni mensaje de aprobación.
- [ ] Solo el móvil del titular confirma; precio y costo provienen del backend.
- [ ] Confirmación válida debita una vez; doble clic, reintento y reinicio no duplican el cargo.
- [ ] Sin confirmar durante 90 segundos, saldo insuficiente, tag desactivado o wallet congelada: no hay débito.
- [ ] Dos cobros concurrentes no sobregiran la wallet.
- [ ] Checkout de pruebas: retorno del navegador no acredita; webhook requiere firma y respuesta canónica válida.
- [ ] Respuesta canónica incorrecta en estado, live_mode, moneda, collector, importe o referencia no acredita.
- [ ] Webhook repetido y conciliación repetida acreditan una sola vez; un pago del proveedor no se reutiliza.
- [ ] Disputa/reembolso detectado congela wallet y genera revisión.
- [ ] Journals balancean cero; modificaciones/borrados y nuevas entradas en journals cerrados se rechazan.
- [ ] Reverso de servicio no prestado exige motivo, revierte contrapartidas y no se duplica.
- [ ] Conciliación sin diferencias; verificar saldo, precio, costo, comisión y margen contra los fixtures usados.

## 6. Prerecargas y actualización en vivo

- [ ] Reserva exige staff y fondos disponibles: reduce saldo del emisor y aún no aumenta el del destinatario.
- [ ] Sin respaldo o con saldo insuficiente, reserva rechazada; reservas concurrentes no sobregiran.
- [ ] Activación acredita una sola vez, incluso en concurrencia; terceros no pueden activarla.
- [ ] Cancelación pendiente devuelve reserva una vez; activada no puede cancelarse por esa vía.
- [ ] Cuenta origen/receptora congelada bloquea activación; cambiar tarjeta conserva reservas.
- [ ] Usuario y administrador reciben cambios por SSE después del commit; rollback no publica movimientos efectivos.
- [ ] SSE exige sesión y aísla wallets; endpoints administrativos exigen staff.
- [ ] Desconectar/reconectar navegador recupera estado actual. Si falla SSE, aparece aviso y consultas cada 5 segundos.
- [ ] Registrar latencias observadas sin presentarlas como SLA del dominio.

## 7. Transporte, monitor y fuentes externas

- [ ] Número guardado muestra sección de transporte aunque NFC esté pendiente.
- [ ] Sin fuente autorizada, transporte conserva saldo desconocido (`null`), nunca cero inventado.
- [ ] Caída/verificación del portal no bloquea OGPASS ni se presenta como saldo obtenido.
- [ ] Monitor NFC muestra únicamente datos autorizados y deja de consultar al cerrarse.
- [ ] Demostración identificada como ficticia; escribir en llavero permanece deshabilitado y no envía comandos.
- [ ] Si se prueba Stellar: Testnet separado de Mainnet y CLP; Mainnet solo lectura; ninguna cifra externa acredita la wallet.

## 8. Cierre y aceptación física

- [ ] Adjuntar logs/capturas sin credenciales e identificar lector/proveedor simulado o físico en cada evidencia.
- [ ] Registrar fallos y bloqueos; no marcar como aprobada una prueba omitida por falta de PostgreSQL, USB o credenciales.
- [ ] Repetir flujo físico de asociación → consulta → solicitud → confirmación en el entorno de pruebas con hardware disponible.
- [ ] Dejar aceptación con dinero real como **pendiente y fuera de esta ronda**. La guía [ACCEPTANCE.md](ACCEPTANCE.md) incluye pasos de pago real que requieren una sesión operativa expresamente autorizada; no ejecutarlos como validación local.

Referencias: [README vigente](../README.md), [entrega histórica](DELIVERY.md).
