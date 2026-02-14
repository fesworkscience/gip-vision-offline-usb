#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

ENV_DIR="${APP_ENV_DIR:-.offline_env}"
WHEEL_DIR="${APP_OFFLINE_WHEELS:-.offline_wheels}"
HOST="${OFFLINE_HOST:-127.0.0.1}"
PORT="${OFFLINE_PORT:-8765}"
STRICT="${OFFLINE_STRICT:-1}"

is_python_ok() {
  local py="$1"

  if [ ! -x "$py" ]; then
    return 1
  fi

  if "$py" -c "import sys; import uvicorn" >/dev/null 2>&1; then
    return 0
  fi

  return 1
}

if is_python_ok "$ENV_DIR/bin/python"; then
  PYTHON="$ENV_DIR/bin/python"
elif is_python_ok "$ENV_DIR/Scripts/python.exe"; then
  PYTHON="$ENV_DIR/Scripts/python.exe"
elif is_python_ok ".venv/bin/python"; then
  PYTHON=".venv/bin/python"
elif is_python_ok ".venv/Scripts/python.exe"; then
  PYTHON=".venv/Scripts/python.exe"
else
  if [ "${STRICT}" != "0" ] && [ ! -d "$WHEEL_DIR" ]; then
    echo "[offline] Не найдено рабочего .offline_env и OFFLINE_STRICT=1."
    echo "[offline] Этот zip собран старой схемой или без .offline_wheels."
    echo "[offline] Переупакуйте релиз с .offline_wheels (локальные wheels) или установите OFFLINE_STRICT=0."
    exit 1
  fi

  echo "[offline] Рабочее offline-окружение не найдено. Собираю локальное окружение..."
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BOOT="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BOOT="python"
  else
    echo "[offline] Не найден python3 в системе. Установите Python 3.11+."
    exit 1
  fi

  rm -rf "$ENV_DIR"
  "$PYTHON_BOOT" -m venv "$ENV_DIR"
  PYTHON="$ENV_DIR/bin/python"
  "$PYTHON" -m pip install --upgrade pip >/dev/null

  if [ -d "$WHEEL_DIR" ] && find "$WHEEL_DIR" -maxdepth 1 -type f -name '*.whl' -print -quit | grep -q .; then
    "$PYTHON" -m pip install --no-index --find-links "$WHEEL_DIR" -r requirements.txt >/dev/null
  elif [ "${STRICT}" = "0" ]; then
    "$PYTHON" -m pip install --no-cache-dir -r requirements.txt >/dev/null
  else
    echo "[offline] OFFLINE_STRICT=1 и в архиве отсутствуют wheels в $WHEEL_DIR."
    echo "[offline] Соберите релиз заново через GitHub Actions, чтобы добавить .offline_wheels."
    exit 1
  fi
fi

exec "$PYTHON" runserver.py --host "$HOST" --port "$PORT" --no-reload "$@"
