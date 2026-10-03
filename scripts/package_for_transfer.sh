#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="$(basename "$ROOT_DIR")"
OUTPUT_PATH="${1:-$(dirname "$ROOT_DIR")/${PROJECT_NAME}-ubuntu-transfer.tar.gz}"

tar \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='**/.pio' \
  --exclude='**/node_modules' \
  --exclude='**/dist' \
  --exclude='**/.env' \
  --exclude='**/.env.local' \
  --exclude='**/.env.supabase' \
  --exclude='**/ogpass_config.h' \
  --exclude='**/*.sqlite3' \
  --exclude='**/*.pem' \
  --exclude='**/*.key' \
  --exclude='**/__pycache__' \
  -czf "$OUTPUT_PATH" \
  -C "$(dirname "$ROOT_DIR")" "$PROJECT_NAME"

echo "Paquete creado sin secretos locales: $OUTPUT_PATH"
