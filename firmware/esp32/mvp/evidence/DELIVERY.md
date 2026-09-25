# Entrega OGPASS — 25 de septiembre de 2026

## Estado real

**MVP implementado y verificado localmente. No hay ninguna parte publicada/verificada en el dominio del usuario.** No se proporcionaron nombre de dominio, DNS, servidor ni credenciales de pago. No se ha realizado un cobro real ni una lectura física en esta sesión.

| Componente | Estado comprobado |
|---|---|
| Django / ledger CLP / web móvil / administración | Implementados. Flujo de navegador y pruebas contables pasan. |
| Mercado Pago | Adaptador de checkout, webhook firmado y consulta canónica implementado. Sin credenciales: recargas reales deshabilitadas. |
| ESP32 + PN532 | Compila con éxito. Binario sin Wi-Fi/token/CA configurados. No hay puerto USB visible; no se flasheó ni se probó un tag físico. |
| Stellar Testnet | Cuenta fondeada con Friendbot y consulta Horizon real: 10.000 XLM de prueba. Sin valor real y sin conexión contable a CLP. |
| Stellar Mainnet | Asociación y consulta pública de solo lectura implementadas. Sin cuenta Mainnet configurada; no hay fondeo ni firmas Mainnet. |
| Transporte | Adaptador desconectado: saldo null. No se afirma saldo ni autorización de un operador de transporte. |
| Dominio / HTTPS | Compose, Caddy, Uvicorn ASGI, variables y migraciones preparados. Dominio y acceso al servidor pendientes. |
| Contenedores | YAML inspeccionado; Docker no está instalado en este entorno. No se ejecutó un build de imagen ni Caddy en servidor. |

## Evidencias

- [45 pruebas PostgreSQL, todas pasan](tests-postgres.txt): duplicados, acceso, CSRF, confirmación, rechazo, reverso, saldo insuficiente, carreras, journals balanceados e inmutables, cierre contable.
- [Prueba Chromium sobre PostgreSQL](tests-browser.txt): 1 prueba completa, sin errores JavaScript ni HTTP 500. Pantalla de 390 px y panel de 1440 px.
- [Datos del recorrido](browser-flow.json), **proveedor y lector simulados dentro de la prueba**, sin fondos reales.
- [40 pruebas SQLite pasan, 5 exclusivas de PostgreSQL omitidas](tests-sqlite.txt).
- [Permisos del usuario runtime](runtime-role.txt): registra un pago en DB aislada; no puede TRUNCATE, desactivar triggers ni alterar sellos de journals.
- [Compilación firmware](firmware-build.txt): SUCCESS, RAM 45.676 / 327.680 bytes; Flash 793.801 / 1.310.720 bytes.
- [Chequeo de despliegue Django](deploy-check.txt): sin advertencias, con variables de validación y no credenciales reales.
- [Consulta real Stellar](stellar-testnet.json): dirección pública y fuente Horizon, timestamp UTC de la consulta. La clave privada Testnet quedó fuera del código en `/tmp/ogpass-stellar-testnet.key`; no se incluye en entregables y no está destinada a producción.

Capturas identificadas expresamente como prueba:

- [Móvil: saldo acreditado](mobile-funded.png)
- [Móvil: confirmar operación](mobile-confirm.png)
- [Móvil: operación registrada](mobile-completed.png)
- [Administrador: conciliación y margen](admin-reconciliation.png)

## Recorrido demostrado

| Paso | Evidencia numérica de prueba |
|---|---:|
| Saldo inicial | $0 CLP |
| Crear recarga y confirmar proveedor controlado | $5.000 CLP |
| Comisión informada por fixture | $100 CLP |
| Saldo después de acreditación | $5.000 CLP |
| Tocar tag mediante protocolo HTTP del lector | Solicitud pendiente; no descuenta |
| Confirmar desde sesión web del titular | Importe $1.000 CLP |
| Costo configurado | $700 CLP |
| Margen de operación | $300 CLP |
| Saldo final usuario | $4.000 CLP |
| Resultado acumulado tras comisión | $200 CLP |
| Diferencia total débitos − créditos | $0 CLP |

Estos valores demuestran la mecánica contable, no rentabilidad comercial real. Antes del lanzamiento deben cargarse costo contractual, precio y credenciales que permitan observar la comisión efectiva. El resultado excluye impuestos y gastos fijos.

## Datos exactos que faltan para activar hoy

1. **Dominio/FQDN:** por ejemplo `app.su-dominio.cl`, su zona DNS y registro A/AAAA hacia el servidor.
2. **Servidor:** IP, usuario SSH y mecanismo de acceso (clave ya configurada o acceso seguro); confirmar Docker + Compose y puertos 80/443. No pegar contraseñas ni claves privadas en el chat.
3. **Mercado Pago Chile:** configurar en `.env` del servidor `MP_ACCESS_TOKEN` de producción, `MP_WEBHOOK_SECRET` y `MP_COLLECTOR_ID`; webhook de tipo payment en `https://DOMINIO/api/payments/webhook/`.
4. **Lector:** conectar ESP32 por USB, identificar puerto y completar `src/ogpass_config.h` con Wi-Fi, token provisionado, URL HTTPS y CA raíz que valida el dominio; tag propio para aceptación física.
5. **Economía de la operación:** confirmar precio y costo reales. Defaults propuestos para demostración: 1000/700 CLP.
6. **Transporte, solo si se quiere esa fuente:** proveedor, API autorizada y credenciales. No bloquea el ledger OGPASS.

[Procedimiento exacto de despliegue y tres terminales](../README.md#despliegue-hoy-preparación-en-servidor).

## Límites operativos explícitos

- Los saldos JSON del prototipo Flask no se importaron como dinero real.
- Asociación de tags mediante lectura, código temporal y sesión del titular; número impreso separado del UID. Consultar no cobra; cada operación de pago exige confirmación móvil. El UID no es una credencial criptográfica de gasto.
- Reverso total solo de servicio no prestado. Disputas/reembolsos externos congelan la cuenta y quedan para conciliación; no hay resolución automática de contracargos ni conciliación bancaria automática.
- Alta Stellar por comando administrativo; activo inicial XLM de Testnet. No hay emisión de token OGPASS ni custodia de claves de usuarios en DB.
- Recuperación por correo pendiente de SMTP; Django admin permite gestionar usuarios.
- Prueba de aceptación real pendiente: checkout pagado con fondos de OGPASS, webhook real, lectura PN532 física, confirmación, registro y conciliación del ID del proveedor.


## Objetivos adicionales: tarjetas, prerrecargas y tiempo real

| Objetivo | Entregado y límite |
|---|---|
| A: escribir una credencial de una tarjeta a otra | No implementado ni probado físicamente. Falta confirmar si se trata de una credencial propia OGPASS o datos originales bip!, y el modelo del tag de destino. El firmware actual lee identificadores; no escribe tarjetas. |
| B: asignar y activar prerrecargas | Implementado para fondos OGPASS: administrador reserva fondos disponibles, destinatario activa una vez, sin vencimiento. Reemplazar el tag conserva el saldo y las reservas de la misma cuenta. No mueve dinero entre titulares ni activa cargas del operador bip!. |
| C: actualización de saldos | SSE sobre ASGI, con PostgreSQL LISTEN/NOTIFY y recuperación al reconectar. Saldos OGPASS actualizados desde el ledger. Stellar mantiene consulta periódica; transporte sigue sin fuente conectada. |

[Prueba real de navegador contra ASGI](tests-realtime.txt) y [mediciones](realtime-flow.json): reserva visible en 555 ms, activación en 288 ms y lectura simulada en 174 ms, en este entorno local. No son garantía de latencia en producción. Se verificaron aislamiento, reemplazo, conservación de prerrecargas, actualización administrativa y reconexión, sin errores JavaScript. Fondos y lector fueron simulados en una base aislada; no se acreditaron fondos ficticios a cuentas reales.

[Vista móvil](realtime-user.png), [administración de prerrecargas](preloads-admin.png) y [guía de aceptación física](ACCEPTANCE.md).

El número **114309782** se usó como etiqueta en pruebas aisladas. No se ha asociado físicamente la tarjeta del usuario. Para asociarla, abrir `/?card_number=114309782#my-card`, leerla y confirmar el código temporal desde la sesión del titular. El lector muestra el saldo OGPASS en el monitor serie; no hay pantalla física configurada. El número impreso por sí solo no permite conocer el saldo bip!.


## Actualización de UI: asociación de nueve dígitos

La UI vigente reemplaza el formulario de tres pasos por ID de nueve dígitos y un botón. La solicitud queda pendiente hasta que un administrador verifica la tarjeta física y confirma una lectura específica en `/ops/`. No se infiere el UID a partir del número ni se muestra asociación sin lectura. El panel muestra lector, última señal, última tarjeta y titular, con consulta cada dos segundos.

El CTA «Copiar y reescribir en la próxima tarjeta NFC» abre un diálogo de función pendiente: escritura física y verificación aún no implementadas. No existe una confirmación de copia exitosa. Se necesita el modelo del tag de destino y definir los datos propios a grabar.

Validación vigente: **49 pruebas PostgreSQL pasan**, 44 SQLite pasan y 5 se omiten por requerir PostgreSQL. La prueba Chromium pasa con solicitud de ID, vinculación administrativa y diálogo de escritura pendiente. Véanse `tests-postgres.txt`, `tests-simple-association.txt`, `tests-browser.txt` y `reader-panel-test.png`. El lector de estas pruebas es simulado; no demuestra conexión física.

El dominio solicitado es `ogpass.xyz`; no se ha desplegado allí. Los reportes anteriores describen los flujos previos y las mediciones de su ejecución.
