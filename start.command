#!/usr/bin/env bash
set -euo pipefail

cd "$(cd "$(dirname "$0")" && pwd)"

export OFFLINE_BLOCK_NET=1
export PIP_NO_INDEX=1
export PIP_DISABLE_PIP_VERSION_CHECK=1
export HTTP_PROXY="http://127.0.0.1:9"
export HTTPS_PROXY="http://127.0.0.1:9"
export ALL_PROXY="socks5://127.0.0.1:9"
export NO_PROXY="localhost,127.0.0.1,::1"
export http_proxy="$HTTP_PROXY"
export https_proxy="$HTTPS_PROXY"
export all_proxy="$ALL_PROXY"
export no_proxy="$NO_PROXY"

if command -v python3 >/dev/null 2>&1; then
  exec python3 start.py "$@"
fi

if command -v python >/dev/null 2>&1; then
  exec python start.py "$@"
fi

echo "[offline] Python is not found. Install Python 3 to run start.py."
exit 1
