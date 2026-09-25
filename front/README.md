# OGPASS Frontend & Web SDK

Módulo web de **OGPASS** diseñado para:
1. **Portal para Usuarios:** Consulta rápida de saldo de tarjetas NFC (por UID o Folio) e historial de viajes/recargas.
2. **Portal de Desarrolladores:** Documentación del SDK, explorador de endpoints (`/authorize`, `/wallet`, `/transactions`), consola de pruebas y simulador de cobros NFC para terminales ESP32.
3. **Panel Administrativo:** Monitoreo de transacciones en tiempo real y métricas del sistema.

## Estructura del Repositorio
- `firmware/`: Código para hardware y lectores NFC (ESP32 + PN532).
- `sandbox/`: API experimental en Python/Flask y bitácoras de pruebas.
- `front/`: Aplicación web y panel de control (React, TypeScript, Tailwind CSS).
