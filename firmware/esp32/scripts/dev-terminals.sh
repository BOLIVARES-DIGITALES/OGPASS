#!/usr/bin/env bash
# Launchers for the numbered VS Code development terminals.
set -euo pipefail

firmware_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
project_dir="$(cd -- "$firmware_dir/../.." && pwd)"
backend_dir="$firmware_dir/mvp"

fail() { printf '%s\n' "$*" >&2; exit 1; }

local_backend() {
  cd -- "$backend_dir"
  [[ -x .venv/bin/python ]] || fail 'Falta mvp/.venv. Consulta mvp/README.md para instalar el entorno Python.'
  # All management commands here use the same isolated development database.
  unset POSTGRES_HOST
  export DEBUG=1
  export SQLITE_PATH="$backend_dir/db.nfc-dev.sqlite3"
  export PUBLIC_URL=http://localhost:3000
  export ALLOWED_HOSTS=localhost,127.0.0.1
  export MP_ACCESS_TOKEN= MP_WEBHOOK_SECRET= MP_COLLECTOR_ID=
  export MOVIRED_BALANCE_API_URL= MOVIRED_BALANCE_API_TOKEN=
}

platformio() {
  cd -- "$firmware_dir"
  if [[ -x "$project_dir/.venv/bin/pio" ]]; then
    pio_bin="$project_dir/.venv/bin/pio"
  else
    pio_bin="$(command -v pio)" || fail 'Falta PlatformIO: instala el entorno indicado en mvp/README.md.'
  fi
}

case "${1:-}" in
  backend)
    local_backend
    printf '%s\n' '01 OGPASS BACKEND | SQLite de desarrollo, pagos reales deshabilitados.' \
      'Usuario: http://localhost:8000/ | Administrador: http://localhost:8000/ops/' \
      'La lectura física necesita HTTPS hacia este mismo backend.'
    .venv/bin/python manage.py migrate --noinput
    exec .venv/bin/python -m uvicorn config.asgi:application --host 127.0.0.1 --port 8000 --reload
    ;;
  frontend)
    cd -- "$project_dir/front_ogpass-sdk-hub"
    command -v npm >/dev/null || fail 'Falta Node.js/npm en PATH. Instálalos antes de iniciar 02 OGPASS FRONTEND.'
    [[ -d node_modules ]] || fail 'Faltan dependencias. Ejecuta npm install en front_ogpass-sdk-hub y vuelve a iniciar esta tarea.'
    printf '%s\n' '02 OGPASS FRONTEND | http://localhost:3000/ | API por proxy al puerto 8000.'
    exec npm run dev -- --host 127.0.0.1 --port 3000 --strictPort
    ;;
  validator)
    platformio
    serial_port="${2:?Indica el puerto USB del lector}"
    [[ -e "$serial_port" ]] || fail "No existe el puerto $serial_port. Ejecuta 06 OGPASS PUERTOS."
    printf '%s\n' '03 OGPASS VALIDATOR | Monitor NFC a 115200 baudios.' \
      'Escribe STATUS, I2CSCAN o SALDO y pulsa Enter. Ctrl+C detiene el monitor.' \
      'Cierra FLASH y cualquier conexión Web Serial antes de iniciar este monitor.'
    exec "$pio_bin" device monitor --port "$serial_port" --baud 115200
    ;;
  flash)
    platformio
    serial_port="${2:?Indica el puerto USB del lector}"
    [[ -e "$serial_port" ]] || fail "No existe el puerto $serial_port. Ejecuta 06 OGPASS PUERTOS."
    printf '%s\n' '04 OGPASS FLASH | Compilar y cargar firmware.' \
      'VALIDATOR y Web Serial deben estar cerrados para liberar el puerto USB.'
    exec "$pio_bin" run -e esp32dev --target upload --upload-port "$serial_port"
    ;;
  health)
    command -v curl >/dev/null || fail 'Falta curl para consultar /health/.'
    printf '%s\n' '05 OGPASS ESTADO | Disponibilidad HTTP local cada 2 segundos; no certifica el lector.'
    trap 'exit 0' INT TERM
    while true; do
      printf '\n[%s] ' "$(date '+%H:%M:%S')"
      if ! curl --fail --silent --show-error --max-time 2 \
        --write-out '\nHTTP %{http_code}\n' http://127.0.0.1:8000/health/; then
        printf '%s\n' 'Backend no disponible o respuesta de error.'
      fi
      sleep 2
    done
    ;;
  ports)
    platformio
    exec "$pio_bin" device list
    ;;
  admin)
    local_backend
    printf '%s\n' '07 OGPASS ADMIN | Crear administrador en db.nfc-dev.sqlite3.'
    .venv/bin/python manage.py migrate --noinput
    exec .venv/bin/python manage.py createsuperuser
    ;;
  *) fail 'Uso: dev-terminals.sh {backend|frontend|validator PUERTO|flash PUERTO|health|ports|admin}' ;;
esac
