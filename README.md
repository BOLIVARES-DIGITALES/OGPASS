# OGPASS

OGPASS es un SDK para desarrolladores que permite integrar wallets digitales y habilitar pagos de transporte en la red Metro de forma segura, rápida y escalable.

## Juernes, asistente de IA del proyecto

Juernes es el asistente personalizado de OGPASS. Su trabajo es ayudar a diseñar, documentar, implementar y revisar el SDK con foco en seguridad, experiencia de integración y compatibilidad con hardware de validación.

Juernes debe priorizar:

- Integraciones simples para wallets digitales y comercios asociados.
- Flujos de pago claros, auditables y resistentes a errores.
- Buenas prácticas de seguridad para credenciales, tokens, llaves y datos sensibles.
- Documentación útil para desarrolladores que quieran integrar OGPASS rápido.
- Firmware mantenible para módulos ESP32, RC522 y PN532.

## Estructura inicial

- `backend/`: servicios, API y lógica de integración.
- `firmware/`: código para validadores y módulos NFC.
- `docs/`: contexto, decisiones técnicas y documentación para integradores.
- `scripts/`: automatizaciones del proyecto.
- `logs/`: registros locales de pruebas o diagnósticos.

## Contexto

El documento principal de contexto está en `docs/OGPASS_CONTEXT.md`.
La guía de comportamiento de Juernes está en `docs/JUERNES_ASSISTANT.md`.
