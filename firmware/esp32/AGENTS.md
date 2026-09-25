# Guía del repositorio

## Estructura

- `src/main.cpp` contiene el firmware ESP32/PN532. `platformio.ini` define el entorno y las dependencias de PlatformIO.
- `src/ogpass_config.example.h` es la plantilla pública de configuración. Guarda las credenciales Wi-Fi reales, los tokens del lector y el certificado CA de despliegue en el archivo local `src/ogpass_config.h`; nunca subas secretos al repositorio.
- `mvp/` contiene la aplicación Django, las plantillas, los recursos estáticos, la configuración de despliegue y las evidencias. Lee `mvp/README.md` antes de cambiar despliegue, ledger, pagos, asociación de tarjetas o comportamiento en tiempo real.
- `evidence/` registra el estado de las verificaciones y la entrega. No presentes pruebas locales como evidencia de un pago real o del comportamiento de un dispositivo físico.

## Reglas de trabajo

- Mantén separadas las responsabilidades del firmware y del backend. El backend es la autoridad para precios, costos, saldos y aprobación de pagos; el lector no debe tratar `pending` como una aprobación.
- Las lecturas NFC normales consultan el saldo OGPASS sin cobrar. Para iniciar un pago se requiere el comando explícito `PAGAR` y la confirmación desde el móvil.
- No infieras ni inventes saldos de tarjetas de transporte externas, no importes saldos del sandbox como fondos reales ni habilites escritura o clonación NFC sin un diseño autorizado explícitamente y validación del hardware.
- Conserva las invariantes contables y de seguridad existentes. No debilites la verificación TLS, la inmutabilidad del ledger, la idempotencia, los controles de propiedad ni la verificación del proveedor de pagos para hacer pasar una prueba.
- Sigue el estilo del módulo correspondiente y limita el alcance de los cambios. Actualiza la documentación o evidencia pertinente cuando cambien el comportamiento o los procedimientos operativos.

## Validación

Desde la raíz del workspace, compila el firmware con:

```bash
pio run
```

Ejecuta las pruebas del backend desde `mvp/` usando el entorno Python configurado para el proyecto:

```bash
python manage.py test core --verbosity 2
```

SQLite se usa para desarrollo; PostgreSQL es necesario para verificar las protecciones contables específicas de la base de datos y el comportamiento concurrente. Consulta `mvp/README.md` para las variables de entorno y la configuración opcional de pruebas de navegador y tiempo real. No ejecutes pagos ni acciones de despliegue en producción como parte de la validación.