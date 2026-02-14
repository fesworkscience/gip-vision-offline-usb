#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

ENV_DIR="${APP_ENV_DIR:-.offline_env}"
WHEEL_DIR="${APP_OFFLINE_WHEELS:-.offline_wheels}"
BOOT_DIR="${APP_BOOT_ENV_DIR:-.offline_boot_env}"
BOOT_PYTHON="${APP_BOOT_PYTHON:-}"
HOST="${OFFLINE_HOST:-127.0.0.1}"
PORT="${OFFLINE_PORT:-8765}"
STRICT="${OFFLINE_STRICT:-1}"

is_python_ok() {
  local py="$1"
  local extra_pythonpath="${2:-}"

  if [ ! -x "$py" ]; then
    return 1
  fi

  if [ -n "$extra_pythonpath" ]; then
    PYTHONPATH="$extra_pythonpath${PYTHONPATH:+:$PYTHONPATH}" "$py" -c "import uvicorn" >/dev/null 2>&1
  else
    "$py" -c "import uvicorn" >/dev/null 2>&1
  fi
}

is_python_311() {
  local py="$1"

  if [ ! -x "$py" ]; then
    return 1
  fi

  "$py" -c "import sys; exit(0 if sys.version_info[:2] == (3, 11) else 1)" >/dev/null 2>&1
}

resolve_boot_python() {
  if [ -n "${BOOT_PYTHON:-}" ] && is_python_311 "$BOOT_PYTHON"; then
    echo "$BOOT_PYTHON"
    return 0
  fi

  if command -v python3.11 >/dev/null 2>&1 && is_python_311 "$(command -v python3.11)"; then
    echo "python3.11"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1 && is_python_311 "$(command -v python3)"; then
    echo "python3"
    return 0
  fi

  return 1
}

build_bootstrap_env() {
  local bootstrap_python="$1"

  if [ -n "${APP_BOOT_ENV_DIR:-}" ]; then
    BOOT_DIR="${APP_BOOT_ENV_DIR}"
    rm -rf "$BOOT_DIR" >/dev/null 2>&1 || true
  else
    BOOT_DIR="$(mktemp -d "${ROOT_DIR}/.offline_boot_XXXXXX")"
  fi

  "$bootstrap_python" -m venv "$BOOT_DIR"
  PYTHON="$BOOT_DIR/bin/python"
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
}

RUN_PYTHONPATH=""
if is_python_ok "$ENV_DIR/bin/python"; then
  PYTHON="$ENV_DIR/bin/python"
elif is_python_ok "$ENV_DIR/Scripts/python.exe"; then
  PYTHON="$ENV_DIR/Scripts/python.exe"
elif is_python_ok ".venv/bin/python"; then
  PYTHON=".venv/bin/python"
elif is_python_ok ".venv/Scripts/python.exe"; then
  PYTHON=".venv/Scripts/python.exe"
else
  FALLBACK_CANDIDATE="$(resolve_boot_python || true)"
  if [ -n "${FALLBACK_CANDIDATE}" ] && is_python_ok "$FALLBACK_CANDIDATE" "$ENV_DIR/lib/python3.11/site-packages"; then
    PYTHON="$FALLBACK_CANDIDATE"
    RUN_PYTHONPATH="$ENV_DIR/lib/python3.11/site-packages"
  else
    if [ "${STRICT}" != "0" ] && [ ! -d "$WHEEL_DIR" ]; then
      echo "[offline] Не найдено рабочего .offline_env и OFFLINE_STRICT=1."
      echo "[offline] Этот zip собран старой схемой или без .offline_wheels."
      echo "[offline] Переупакуйте релиз с .offline_wheels (локальные wheels) или установите OFFLINE_STRICT=0."
      exit 1
    fi

    if [ -z "${FALLBACK_CANDIDATE}" ]; then
      FALLBACK_CANDIDATE="$(resolve_boot_python || true)"
    fi
    if [ -z "${FALLBACK_CANDIDATE}" ]; then
      echo "[offline] Не найден python3.11 для офлайн-старта."
      echo "[offline] Установите Python 3.11 или используйте release, собранный с совместимым окружением."
      exit 1
    fi

    echo "[offline] Рабочее offline-окружение не найдено. Собираю локальное окружение..."
    build_bootstrap_env "$FALLBACK_CANDIDATE"
  fi
fi

if [ -n "$RUN_PYTHONPATH" ]; then
  PYTHONPATH="$RUN_PYTHONPATH${PYTHONPATH:+:$PYTHONPATH}" exec "$PYTHON" runserver.py --host "$HOST" --port "$PORT" --no-reload "$@"
else
  exec "$PYTHON" runserver.py --host "$HOST" --port "$PORT" --no-reload "$@"
fi
