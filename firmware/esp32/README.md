# OGPASS · base de lanzamiento y laboratorio

El único MVP de lanzamiento está en [mvp/](mvp/README.md): Django, frontend del
mismo origen, identidad, wallet, ledger y eventos SSE. La evolución progresiva
está documentada en [arquitectura](mvp/docs/ARCHITECTURE.md).

## Hardware vigente

- **RC522 PRIMARY**, SPI: SS5, SCK18, MISO19, MOSI23, RST27; IRQ libre.
- **PN532 OPTIONAL**, I2C: SDA21/SCL22. Solo diagnóstico, timeout de 40 ms,
  tarea independiente. No se espera al módulo opcional en setup/loop principal.
- **BLE iBeacon**, experimento optativo; no activo en el firmware normal.

`src/main.cpp` ensambla drivers de `mvp/hardware/`, ReaderManager y transporte
HTTPS en otra tarea. Ningún driver contiene identidad, precio, wallet o ledger.
Consultar no cobra; este firmware no habilita pagos, escritura ni emulación.
Las APIs previas de pago permanecen en el backend con confirmación móvil.

```bash
pio run                        # firmware normal, RC522 principal
pio run -e esp32developer       # metadatos de diagnóstico por serie
pio run -e ble_ibeacon          # laboratorio BLE, no promoción comercial
```

Comandos serie a 115200: `STATUS`, `I2CSCAN`, `SALDO`. `I2CSCAN` agenda el probe
opcional; consultar `STATUS` después. Un ACK I2C no demuestra lectura NFC PN532.
Un fallo eléctrico compartido puede afectar todo el circuito y requiere pruebas
físicas; el aislamiento de tareas no sustituye esa validación.

Configuración de red privada: `src/ogpass_config.h`, nunca versionada. La plantilla
es `src/ogpass_config.example.h`. Sin configuración, funciona la detección local;
no se conecta al backend. Con red, exige HTTPS, CA válida y reloj sincronizado.
NVS conserva un evento en vuelo antes de enviarlo; la cola RAM no es persistente.

## Validación

```bash
cd mvp
DEBUG=1 .venv/bin/python manage.py test core --verbosity 2
.venv/bin/python scripts/verify_launch_browser.py
```

[Estado del sprint y límites](mvp/evidence/launch-20261011/SPRINT.md).
La compilación, los mocks y los tests locales no certifican lecturas físicas,
recepción BLE, pagos reales ni despliegue en producción.

[Laboratorio](mvp/prototipos/README.txt): solo fichas .txt. Emulación, LF/UWB y
Find My son investigación; no forman parte de la autorización ni del ledger.
