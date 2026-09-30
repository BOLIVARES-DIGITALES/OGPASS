# Checklist de lanzamiento — OGPASS

**Propósito:** verificar que OGPASS puede operar de forma segura con saldo propio OGPASS, lector NFC y pagos. Este documento no autoriza ni afirma integración con saldo, carga, escritura o clonación de tarjetas de transporte externas.

**Regla de salida:** no marcar una tarea como completada sin evidencia fechada, responsable y enlace al resultado. Las pruebas locales, los fixtures y los lectores simulados no sustituyen una prueba física ni un cobro real.

## Estado inicial conocido

- [x] MVP local: ledger CLP, web móvil, administración, asociación de tarjeta, prerrecargas, SSE y pruebas automatizadas.
- [x] Consulta Stellar Testnet demostrada; Mainnet es solo lectura y no está configurada.
- [ ] Dominio `ogpass.xyz`, servidor, DNS, HTTPS y credenciales productivas verificados.
- [ ] Cobro real, webhook real y lectura física PN532 verificados de punta a punta.
- [ ] Integración autorizada con un operador de transporte. Hasta entonces, `transport.status` debe ser `not_connected` y el saldo externo debe ser `null`.

## 1. Gobierno y alcance

- [ ] **OG:** confirmar el caso de uso de lanzamiento: saldo OGPASS, recargas, pago de servicio y/o prerrecargas.
- [ ] **OG + Legal/Operaciones:** documentar qué servicio se considera “prestado” y en qué condiciones se permite un reverso.
- [ ] **OG:** aprobar precio y costo contractual por lector. No usar los valores de demostración (`1000 / 700 CLP`) como decisión comercial.
- [ ] **CTO:** confirmar que el lanzamiento no ofrece, anuncia ni simula saldo, escritura, copia o recarga de una tarjeta de transporte externa.
- [ ] **CIO:** nombrar responsable de la operación diaria, conciliación y respuesta a incidentes.

## 2. Producción, red y secretos

- [ ] Tener VPS Linux con Docker Compose, acceso seguro por SSH y puertos TCP 80/443 disponibles.
- [ ] Apuntar DNS de `ogpass.xyz` al servidor y comprobar resolución desde una red externa.
- [ ] Configurar HTTPS válido y confirmar que el lector valida la cadena de certificados; está prohibido desactivar TLS.
- [ ] Crear `.env` solo en el servidor con permisos restrictivos; no subirlo al repositorio ni pegar secretos en chats.
- [ ] Generar secretos diferentes para Django, PostgreSQL, administrador de PostgreSQL y cada lector.
- [ ] Confirmar que el usuario de aplicación no es superusuario y no puede alterar, truncar o desactivar los controles del ledger.
- [ ] Ejecutar migraciones y `manage.py check --deploy` en producción antes de abrir tráfico.
- [ ] Crear y probar un backup cifrado fuera del servidor y una restauración en una base de datos aislada.

## 3. Mercado Pago y contabilidad

- [ ] Configurar `MP_ACCESS_TOKEN`, `MP_WEBHOOK_SECRET` y `MP_COLLECTOR_ID` de producción en el servidor.
- [ ] Registrar el webhook de tipo **payment** en la URL HTTPS productiva.
- [ ] Confirmar que solo un pago `approved`, live, en CLP, del collector correcto y con importe/referencia exactos acredita fondos.
- [ ] Confirmar que la URL de retorno del checkout no acredita ninguna recarga.
- [ ] Ejecutar una recarga real de importe controlado y guardar: ID del proveedor, importe, comisión, webhook y journal asociado.
- [ ] Conciliar el pago en `/ops/`; verificar que el saldo por cobrar no se presenta como saldo bancario liquidado.
- [ ] Probar pago duplicado, webhook repetido, pago rechazado, pago pendiente, reembolso y contracargo; verificar idempotencia y congelamiento para revisión cuando corresponda.
- [ ] Ejecutar `reconcile` y verificar que todos los journals cuadran y no hay asientos modificados o eliminados.

## 4. Tarjeta NFC y lector físico

- [ ] Conectar el ESP32 y PN532 físicos; confirmar lectura en monitor serie y heartbeat del lector en `/ops/`.
- [ ] Configurar Wi‑Fi, URL HTTPS, token provisionado y CA válida en `ogpass_config.h`, fuera del control de versiones.
- [ ] Asociar una tarjeta propia: número impreso → solicitud pendiente → lectura física concreta → verificación administrativa → confirmación.
- [ ] Verificar que el número impreso y UID se almacenan como datos distintos; el UID no se deriva del número impreso.
- [ ] Retirar y volver a acercar el tag: debe mostrar el saldo **OGPASS** actual, fuente y fecha, sin crear operación ni journal de pago.
- [ ] Probar tag desconocido, tag desactivado, lector desconectado y lectura expirada; no debe asociarse ni cobrar nada.
- [ ] Enviar `PAGAR`, acercar el tag y confirmar en el móvil. Un resultado `pending` no es autorización.
- [ ] Probar doble toque, doble confirmación, corte de red y reinicio del lector; debe conservar la referencia y no generar doble débito.
- [ ] Probar saldo insuficiente y vencimiento de 90 segundos; no debe debitar fondos.
- [ ] Verificar que reemplazar una tarjeta desactiva la anterior y conserva wallet, saldo y prerrecargas.

## 5. Datos, saldo y tiempo real

- [ ] Confirmar que el saldo mostrado se recalcula desde el ledger autorizado, no desde un valor enviado por el lector ni desde un caché de navegador.
- [ ] Verificar que cada consulta de tarjeta normal se registra como `CardScan` con propósito `balance` y no crea `Operation` ni `Journal`.
- [ ] Verificar que una operación de pago conserva UID, lector, importe, costo, estado, fecha, referencia idempotente y journal.
- [ ] Comprobar que eventos `WalletEvent` se crean en la misma transacción que el cambio de saldo y se emiten solo después del commit.
- [ ] Abrir dos sesiones del usuario y una administrativa; comprobar actualización vía SSE tras recarga, activación, pago, reverso y reemplazo.
- [ ] Desconectar y reconectar una sesión; la UI debe volver a consultar el estado autorizado y advertir que no puede mostrar una cifra vieja como actual.
- [ ] Verificar que las rutas de eventos y operaciones respetan sesión, propiedad de wallet y permisos de staff.
- [ ] Revisar logs y auditoría de asociación, escaneos, pagos, reversos y conciliación.

## 6. Prerrecargas y reversos

- [ ] Acreditar fondos reales al administrador antes de permitir una prerrecarga.
- [ ] Crear una prerrecarga y comprobar que los fondos quedan reservados al emisor, no disponibles para gasto.
- [ ] Activarla con doble clic o solicitudes simultáneas; debe acreditarse una sola vez al usuario.
- [ ] Cambiar el tag asociado y comprobar que la prerrecarga pendiente y el saldo permanecen en la wallet del usuario.
- [ ] Cancelar una prerrecarga pendiente y comprobar la contrapartida completa; intentar cancelar una ya activada y confirmar que se rechaza.
- [ ] Reversar únicamente un servicio no prestado, con motivo y usuario responsable; comprobar asientos opuestos vinculados al original.

## 7. Stellar y fuentes externas

- [ ] Mantener Stellar Mainnet en solo lectura hasta una aprobación explícita de OG para cualquier capacidad transaccional.
- [ ] Verificar que Testnet y Mainnet se identifican y consultan de forma separada; no mezclar redes ni presentar XLM como saldo CLP.
- [ ] No almacenar claves privadas de Stellar en la base de datos o repositorio; documentar la custodia de cada clave fuera del sistema.
- [ ] Mantener el transporte externo como `not_connected` hasta contar con proveedor, autorización, documentación técnica y credenciales válidas.
- [ ] No ejecutar escritura, copia de UID, clonación o modificación de tarjetas ajenas. Una futura credencial OGPASS propia requiere diseño y validación física independientes.

## 8. Pruebas y evidencia de salida

- [ ] Ejecutar suite Django sobre PostgreSQL de prueba, incluyendo concurrencia, inmutabilidad y balance de journals.
- [ ] Ejecutar pruebas de navegador en móvil y escritorio contra PostgreSQL aislado.
- [ ] Compilar firmware y guardar hash de binario, versión, configuración no sensible y resultado del flasheo.
- [ ] Ejecutar el recorrido físico completo con una tarjeta propia y un pago real controlado.
- [ ] Guardar capturas, IDs de transacción, logs redaccionados y resultado de `reconcile` bajo `mvp/evidence/`.
- [ ] Registrar incidente, responsable, impacto y corrección de cualquier paso fallido antes de reintentar.
- [ ] **OG:** revisar evidencia y aprobar por escrito el paso de piloto cerrado a lanzamiento.

## Criterio de aprobación del piloto

El piloto queda listo únicamente cuando un usuario puede recargar con un pago real confirmado, consultar saldo OGPASS con un lector físico sin cobro, iniciar un pago solo mediante `PAGAR` y confirmación móvil, y cuando la conciliación demuestra que los asientos cierran. Transporte externo, tarjetas ajenas y Stellar Mainnet no forman parte de este criterio.
