# OGPASS · ESP32 + PN532 y MVP

La implementación completa está en [mvp/README.md](mvp/README.md): arquitectura, despliegue, variables, pruebas y comandos para las tres terminales.

- Firmware: `src/main.cpp`, ESP32 I2C GPIO21/22 + PN532; TLS, token por lector, idempotencia persistente y consulta sin cobro, asociación por código y pago con confirmación móvil.
- Configuración privada: copiar `src/ogpass_config.example.h` a `src/ogpass_config.h` y completar Wi-Fi, dominio HTTPS, token y CA. No subir credenciales.
- Backend/web: Django + PostgreSQL + Uvicorn/ASGI en `mvp/`, con prerecargas respaldadas y eventos SSE.
- Estado y evidencias: [mvp/evidence/DELIVERY.md](mvp/evidence/DELIVERY.md).

No se modificó el prototipo Flask ni se importaron sus saldos JSON como dinero real.
