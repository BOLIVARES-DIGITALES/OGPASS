"""Fail closed when private ESP32 configuration is absent or incomplete."""

import re
from pathlib import Path

try:
    Import("env")  # type: ignore[name-defined]  # Provided by PlatformIO/SCons.
    PROJECT_DIR = Path(env["PROJECT_DIR"])  # type: ignore[name-defined]
except NameError:
    PROJECT_DIR = Path(__file__).resolve().parents[1]

config_path = PROJECT_DIR / "src" / "ogpass_config.h"
issues = []

if not config_path.exists():
    issues.append("falta src/ogpass_config.h; copia src/ogpass_config.example.h")
    content = ""
else:
    content = config_path.read_text(encoding="utf-8")


def macro(name):
    match = re.search(rf'^#define\s+{name}\s+"([^"]*)"', content, re.MULTILINE)
    return match.group(1).strip() if match else ""


ssid = macro("OGPASS_WIFI_SSID")
password = macro("OGPASS_WIFI_PASSWORD")
api_base = macro("OGPASS_API_BASE")
reader_token = macro("OGPASS_READER_TOKEN")

if not ssid or ssid.startswith("TU_"):
    issues.append("completa OGPASS_WIFI_SSID con una red Wi-Fi 2,4 GHz")
if not password or password.startswith("TU_"):
    issues.append("completa OGPASS_WIFI_PASSWORD")
if not api_base.startswith("https://") or "TU_DOMINIO" in api_base or api_base.endswith("/"):
    issues.append("OGPASS_API_BASE debe ser HTTPS, real y sin barra final")
if len(reader_token) < 32 or reader_token.startswith("TU_"):
    issues.append("OGPASS_READER_TOKEN debe ser el token privado provisionado (mínimo 32 caracteres)")
if (
    "-----BEGIN CERTIFICATE-----" not in content
    or "-----END CERTIFICATE-----" not in content
    or "REEMPLAZAR_POR_CA_RAIZ" in content
):
    issues.append("reemplaza OGPASS_ROOT_CA por la CA raíz PEM completa")

if issues:
    raise SystemExit("Configuración OGPASS incompleta:\n- " + "\n- ".join(issues))

print("Configuración OGPASS: estructura privada validada (secretos no mostrados).")
