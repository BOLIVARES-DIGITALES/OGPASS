# Contexto de OGPASS

## Vision

OGPASS busca ser una capa de integracion para pagos de transporte en Metro usando wallets digitales, validadores NFC y servicios backend seguros.

## Producto

El proyecto se plantea como un SDK para desarrolladores. Debe permitir que una wallet digital o aplicacion asociada pueda integrar pagos de transporte sin tener que construir desde cero la comunicacion con validadores, backend de autorizacion y flujos de conciliacion.

## Usuarios principales

- Desarrolladores que integran wallets digitales.
- Equipos que operan infraestructura de validacion.
- Equipos de backend que necesitan procesar autorizaciones, eventos y conciliacion.
- Operadores o administradores que revisan logs, estados y metricas.

## Componentes esperados

- SDK de integracion para wallets o apps cliente.
- Backend para tokens, autorizaciones, validaciones y conciliacion.
- Firmware para hardware basado en ESP32 y lectores NFC.
- Documentacion para integradores.
- Scripts para pruebas, simulacion y diagnostico.

## Hardware objetivo

- ESP32 como controlador principal.
- RC522 como lector NFC economico para prototipos.
- PN532 como lector NFC mas completo para pruebas avanzadas.

## Flujos clave

1. Registro o vinculacion de wallet.
2. Emision de token de viaje o credencial temporal.
3. Lectura NFC en validador.
4. Validacion online u offline segun disponibilidad.
5. Confirmacion de acceso.
6. Registro de evento para auditoria y conciliacion.

## Supuestos iniciales

- El repositorio aun esta en fase inicial.
- La seguridad del flujo de pago es un requisito central.
- La experiencia de integracion debe ser simple y bien documentada.
- Los ejemplos deben poder ejecutarse localmente antes de conectar hardware real.

## Asistente del proyecto

El asistente personalizado del proyecto se llama Juernes. Su guia esta en `docs/JUERNES_ASSISTANT.md`.
