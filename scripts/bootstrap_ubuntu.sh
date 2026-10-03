#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
FIRMWARE_DIR="$ROOT_DIR/firmware/esp32"
MVP_DIR="$FIRMWARE_DIR/mvp"

for command_name in python3 git; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Falta $command_name. Instala primero los paquetes indicados en UBUNTU_SETUP.md."
    exit 1
  fi
done

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/pip" install platformio
"$VENV_DIR/bin/pip" install -r "$MVP_DIR/requirements.txt"

if [[ ! -f "$FIRMWARE_DIR/src/ogpass_config.h" ]]; then
  cp "$FIRMWARE_DIR/src/ogpass_config.example.h" "$FIRMWARE_DIR/src/ogpass_config.h"
  chmod 600 "$FIRMWARE_DIR/src/ogpass_config.h"
  echo "Creado firmware/esp32/src/ogpass_config.h: completa sus credenciales locales."
fi

if [[ ! -f "$MVP_DIR/.env" ]]; then
  cp "$MVP_DIR/supabase.env.example" "$MVP_DIR/.env"
  chmod 600 "$MVP_DIR/.env"
  echo "Creado firmware/esp32/mvp/.env: completa los valores REPLACE_WITH_*."
fi

if id -nG "$USER" | tr ' ' '\n' | grep -qx dialout; then
  echo "Permiso serial dialout: OK"
else
  echo "Permiso serial pendiente: sudo usermod -aG dialout $USER"
  echo "Después cierra sesión y vuelve a entrar."
fi

echo
echo "Base Ubuntu preparada. Próximo paso: consulta UBUNTU_SETUP.md."
