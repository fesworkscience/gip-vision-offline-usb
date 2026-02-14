@echo off
setlocal

cd /d %~dp0
if defined APP_ENV_DIR (
  set "ENV_DIR=%APP_ENV_DIR%"
) else (
  set "ENV_DIR=config\.offline_env"
)

set "HOST=127.0.0.1"
if defined OFFLINE_HOST set "HOST=%OFFLINE_HOST%"
set "PORT=8765"
if defined OFFLINE_PORT set "PORT=%OFFLINE_PORT%"
set "PYTHON=%ENV_DIR%\Scripts\python.exe"
set "OFFLINE_BLOCK_NET=1"
set "PIP_NO_INDEX=1"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "HTTP_PROXY=http://127.0.0.1:9"
set "HTTPS_PROXY=http://127.0.0.1:9"
set "ALL_PROXY=socks5://127.0.0.1:9"
set "NO_PROXY=localhost,127.0.0.1,::1"
set "http_proxy=%HTTP_PROXY%"
set "https_proxy=%HTTPS_PROXY%"
set "all_proxy=%ALL_PROXY%"
set "no_proxy=%NO_PROXY%"

if not exist "%PYTHON%" (
  echo [offline] Не найдено встроенное окружение: %PYTHON%
  echo [offline] Переупакуйте релиз заново.
  exit /b 1
)

"%PYTHON%" -m app.offline_runner --host %HOST% --port %PORT% %*
