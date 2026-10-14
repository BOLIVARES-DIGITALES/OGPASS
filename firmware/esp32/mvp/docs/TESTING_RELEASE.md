# Verificación y release candidate

## Desarrollo y configuración

Desde `mvp/` con el entorno Python del proyecto:

```bash
DEBUG=1 OGPASS_ENV=development .venv/bin/python manage.py migrate
DEBUG=1 OGPASS_ENV=development OGPASS_MODE=product .venv/bin/python -m uvicorn config.asgi:application --host 127.0.0.1 --port 8000
```

Usar `SQLITE_PATH` si se quiere una DB local separada. No copiar DBs entre ambientes.
Para diagnóstico, `OGPASS_MODE=developer` y una sesión staff. Producción exige
PostgreSQL, DEBUG=0, HTTPS y credenciales locales; jamás cargar `.env` mediante
un comando que imprima su contenido.

Los lanzadores numerados mantienen 01 BACKEND, 02 FRONTEND, 03 VALIDATOR,
04 FLASH y 05 ESTADO. FRONTEND abre ahora el MVP en 8000; no necesita Node.
FLASH es manual y exige cerrar monitor/Web Serial. Compilar no flashea hardware.

## Pruebas repetibles

```bash
# Desde firmware/esp32
pio run
pio run -e esp32developer
pio run -e ble_ibeacon
pio run -e network_compile_test   # cobertura TLS/NVS, NO cargar este firmware

g++ -std=c++11 -Wall -Wextra -Werror mvp/hardware/tests/reader_manager_test.cpp -o /tmp/ogpass-reader-test
/tmp/ogpass-reader-test

# Desde mvp, sin POSTGRES_HOST para SQLite:
env -u POSTGRES_HOST DEBUG=1 OGPASS_ENV=test .venv/bin/python manage.py test core --verbosity 2
# Con conexión exportada a PostgreSQL exclusivo de pruebas:
DEBUG=1 OGPASS_ENV=test .venv/bin/python manage.py test core --verbosity 2

.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python scripts/verify_launch_browser.py
# PostgreSQL temporal por socket local /tmp/ogpass-*:
# Exportar OGPASS_TEST_POSTGRES_HOST, OGPASS_TEST_POSTGRES_PORT y opcionalmente USER.
.venv/bin/python scripts/verify_launch_browser.py --postgres

# Recorrido histórico completo sin sobrescribir evidencia previa:
OGPASS_EVIDENCE_DIR="$PWD/evidence/nueva-ronda-browser" DEBUG=1 .venv/bin/python manage.py test core.browser_tests --verbosity 2
```

Los tests automáticos usan fuentes controladas y bases aisladas; no prueban
pagos reales, lectura física ni emisión RF. SQLite omite pruebas de bloqueo de
filas y triggers contables. El navegador v1 prueba 375/390/430/768/1440 px,
SSE real, datos privados y eventos HTTP de lector simulado.

## Migraciones, Docker y rollback

`0009` añade identidad, credenciales, dispositivos y eventos; `0010` crea
identidades para cuentas existentes sin cambiar sus movimientos ni saldos.
Respaldar y probar restauración en una DB separada antes de operar en producción.
El app label y las migraciones contables anteriores no se renombraron.

Compose ejecuta el servicio migrador antes del backend; el runtime no ejecuta
migraciones con el rol de aplicación. Fuera de Compose hay que ejecutar
`python manage.py migrate --noinput` como paso separado y con el rol migrador.
Dockerfile conserva `config.asgi` mediante wrapper y recolecta los recursos del
nuevo `frontend/`. Las claves de credenciales se transmiten explícitamente al
runtime; no están incluidas en la imagen.

En una máquina con Docker, usando exclusivamente configuración de pruebas:

```bash
docker compose config --quiet
docker compose build backend migrate
```

No ejecutar pagos, cambios DNS ni despliegues reales como validación. Para rollback
conservar la DB y volver al código compatible; las tablas nuevas pueden quedarse.
No revertir migraciones contables ni eliminar volúmenes para recuperar código.

## Gate pendiente de hardware / operación

- RC522: confirmar identificación y retirada/repetición con tags propios.
- PN532: ausente, SDA/SCL defectuosos y timeouts sin detener RC522 ni API.
- BLE: verificar RF, recepción/calibración RSSI, consumo y coexistencia; la
  compilación con red simultánea puede requerir otra partición y debe medirse.
- Red: CA inválida, pérdida WiFi, reintento, reinicio NVS y cola llena.
- Identidad: validar propietario y número impreso; no autorizar por UID/beacon.
- Despliegue: build de imagen, arranque Compose, TLS y restauración de backup.

Hasta cerrar estos puntos, la entrega es una base candidata de software, no una
certificación de lanzamiento físico/comercial. Gate de promoción: prototipos/07.
