# Aceptación física pendiente — OGPASS

Las pruebas automáticas usan fondos y lector simulados. Esta lista debe ejecutarse con el ESP32 conectado, PN532 detectado, HTTPS válido y un proveedor de pagos real configurado.

1. Registrar la cuenta usuaria y una cuenta administradora. Confirmar que ambas parten sin fondos creados por el sistema.
2. Actualizar firmware y configuración privada. Verificar heartbeat del lector y detección de PN532 en monitor serie.
3. En «Mi tarjeta», introducir `114309782`. Pulsar Asociar tarjeta y acercar la tarjeta propia. En `/ops/`, seleccionar la solicitud y confirmar el UID leído tras comprobar titular y número impreso. Comprobar que el UID leído se guardó separado del número impreso. No afirmar asociación física antes de este paso.
4. Retirar y volver a acercar. Debe mostrar el saldo OGPASS disponible, la fuente y fecha; cero si no hay acreditaciones. No debe crear operaciones de pago ni asientos.
5. Pagar una recarga real en la cuenta administradora con fondos de OGPASS. Esperar webhook y verificar ID e importe en Mercado Pago. Una URL de retorno no debe acreditar.
6. Desde `/ops/`, reservar una prerecarga para el usuario. El administrador pierde ese importe disponible; el usuario ve una prerecarga pendiente y todavía no lo puede gastar.
7. Activar desde la UI usuaria dos veces rápidamente: una sola acreditación. Verificar ambas pantallas en vivo y conciliación cero.
8. Consultar con la tarjeta. Ver el nuevo saldo sin cobro. La información es del ledger OGPASS, no saldo bip!.
9. Crear otra prerecarga pendiente. Asociar una tarjeta propia diferente a la misma cuenta con el nuevo flujo. Desactivar la anterior desde Django admin; fondos y prerecarga pendiente permanecen intactos en la cuenta.
10. Desconectar el navegador y hacer una operación desde otra sesión autorizada; reconectar y verificar el estado actual. El aviso de desconexión debe impedir interpretar una cifra vieja como actual.
11. Cortar red del lector durante una solicitud y reiniciarlo. Tras recuperar conexión, debe conservar referencia y propósito; no crear doble cobro.
12. Enviar `PAGAR` por monitor, acercar la tarjeta y confirmar en el móvil. Comprobar importe, costo, margen, saldo final e idempotencia.
13. No confirmar durante 90 s, probar fondos insuficientes y tag desactivado: no deben debitarse fondos.
14. Reversar solo un servicio no prestado y comprobar contrapartidas, motivo y resultado acumulado.

**Copia/escritura:** no ejecutar comandos de escritura sobre una bip!. Esa función no está implementada; faltan modelo de destino y definición de la credencial OGPASS propia. Ninguna prueba automática acredita activación de cargas del operador ni transferencia de saldo bip!.

**Dominio:** `ogpass.xyz` fue indicado por el usuario; siguen pendientes servidor, DNS y acceso. Repetir la aceptación allí; la latencia local no demuestra la latencia de producción.
