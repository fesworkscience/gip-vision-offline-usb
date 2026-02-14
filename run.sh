#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

ENV_DIR="${APP_ENV_DIR:-.offline_env}"
HOST="${OFFLINE_HOST:-127.0.0.1}"
PORT="${OFFLINE_PORT:-8765}"
STRICT="${OFFLINE_STRICT:-1}"

if [ -x "$ENV_DIR/bin/python" ]; then
  PYTHON="$ENV_DIR/bin/python"
elif [ -x "$ENV_DIR/Scripts/python.exe" ]; then
  PYTHON="$ENV_DIR/Scripts/python.exe"
else
  if [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
  elif [ -x ".venv/Scripts/python.exe" ]; then
    PYTHON=".venv/Scripts/python.exe"
  else
    if [ "${STRICT}" != "0" ]; then
      echo "[offline] В этом zip не найдено вшитое окружение .offline_env."
      echo "[offline] Для офлайн-режима создайте релизную сборку заново или скопируйте каталог .offline_env."
      echo "[offline] Для локальной разработки включите OFFLINE_STRICT=0 (будет выполнен bootstrap)."
      exit 1
    fi

    echo "[offline] В пакете не найдено окружение. Инициализирую fallback окружение..."
    if command -v python3 >/dev/null 2>&1; then
      PYTHON_BOOT="python3"
    elif command -v python >/dev/null 2>&1; then
      PYTHON_BOOT="python"
    else
      echo "[offline] Не найдено ни .offline_env, ни python3. Установите Python 3.11+ или используйте готовый релиз."
      exit 1
    fi
    "$PYTHON_BOOT" -m venv "$ENV_DIR"
    source "$ENV_DIR/bin/activate"
    "$ENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
    "$ENV_DIR/bin/python" -m pip install --no-cache-dir -r requirements.txt >/dev/null
    PYTHON="$ENV_DIR/bin/python"
    exec "$PYTHON" runserver.py --host "$HOST" --port "$PORT" "$@"
  fi
fi

exec "$PYTHON" runserver.py --host "$HOST" --port "$PORT" --no-reload "$@"
