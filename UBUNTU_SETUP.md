# OGPASS en Ubuntu: preparación y prueba del lector

Esta guía prepara otra máquina sin copiar secretos ni artefactos generados.

## 1. Paquetes base

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip build-essential curl ca-certificates
sudo usermod -aG dialout "$USER"
```

Cierra sesión y vuelve a entrar para aplicar el grupo `dialout`.

## 2. Copiar o clonar el repositorio

Opción Git recomendada:

```bash
git clone URL_DEL_REPOSITORIO OGPASS
cd OGPASS
git switch dev
```

Si se copia directamente desde otro equipo, no transfieras `.venv`, `.pio`, `.env`, `ogpass_config.h`, claves PEM, bases SQLite ni `node_modules`.

Para crear desde el equipo actual un paquete sanitizado:

```bash
./scripts/package_for_transfer.sh
```

El archivo resultante excluye credenciales, entornos virtuales y artefactos generados. Las credenciales necesarias deben cargarse por separado y guardarse únicamente en los archivos locales ignorados por Git.

## 3. Preparar dependencias y plantillas

```bash
cd OGPASS
chmod +x scripts/bootstrap_ubuntu.sh
./scripts/bootstrap_ubuntu.sh
```

Completa localmente, sin subirlos a Git:

- `firmware/esp32/src/ogpass_config.h`
- `firmware/esp32/mvp/.env`

## 4. Verificar el ESP32

Conecta el ESP32 mediante un cable USB de datos:

```bash
.venv/bin/pio device list
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
```

El CP2102 normalmente aparece como `/dev/ttyUSB0`.

## 5. Compilar, cargar y monitorear

```bash
cd firmware/esp32
../../.venv/bin/pio run -e esp32dev
../../.venv/bin/pio run -e esp32dev -t upload --upload-port /dev/ttyUSB0
../../.venv/bin/pio device monitor --port /dev/ttyUSB0 --baud 115200
```

En el monitor serie puedes enviar:

```text
I2CSCAN
STATUS
SALDO
```

El PN532 correcto debe informar `OGPASS_I2C_DEVICE 0x24`. La lectura normal es únicamente consulta; los pagos permanecen deshabilitados con `OGPASS_ALLOW_PAYMENTS 0`.

## 6. Tres terminales de diagnóstico

Terminal 1 — lector:

```bash
cd OGPASS/firmware/esp32
../../.venv/bin/pio device monitor --port /dev/ttyUSB0 --baud 115200
```

Terminal 2 — interfaz local:

```bash
while true; do curl -fsS -o /dev/null -w 'local HTTP %{http_code} %{time_total}s\n' http://127.0.0.1:8080/ || echo 'local sin respuesta'; sleep 5; done
```

Terminal 3 — API:

```bash
while true; do curl -fsS --max-time 15 https://api.ogpass.xyz/health/ || echo 'API sin respuesta'; echo; sleep 10; done
```

No abras Web Serial en el navegador mientras PlatformIO usa el puerto: solamente un proceso puede controlarlo a la vez.

## 7. Validación antes de continuar

```bash
git status --short
git diff --check
cd firmware/esp32 && ../../.venv/bin/pio run -e esp32dev
```

No ejecutes pagos reales durante estas pruebas. Primero confirma `reader_ready=true`, Wi-Fi y `backend_online=true` mediante `STATUS`.
