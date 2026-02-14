@echo off
setlocal

cd /d %~dp0
if defined APP_ENV_DIR (
  set "ENV_DIR=%APP_ENV_DIR%"
) else (
  set "ENV_DIR=.offline_env"
)

set "HOST=127.0.0.1"
if defined OFFLINE_HOST set "HOST=%OFFLINE_HOST%"
set "PORT=8765"
if defined OFFLINE_PORT set "PORT=%OFFLINE_PORT%"
if defined OFFLINE_STRICT (
  set "OFFLINE_STRICT=%OFFLINE_STRICT%"
) else (
  set "OFFLINE_STRICT=1"
)

if exist "%ENV_DIR%\Scripts\python.exe" (
  set "PYTHON=%ENV_DIR%\Scripts\python.exe"
  goto run
)

if exist .venv\Scripts\python.exe (
  set "PYTHON=%CD%\.venv\Scripts\python.exe"
  goto run
)

if not "%OFFLINE_STRICT%"=="0" (
  echo [offline] В этом zip не найдено вшитое окружение .offline_env.
  echo [offline] Для офлайн-режима используйте zip с включенным окружением.
  echo [offline] Для локальной разработки установите OFFLINE_STRICT=0.
  exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
  echo [offline] Не найден python для bootstrap. Установите Python 3.11+ или скопируйте .offline_env.
  exit /b 1
)

echo [offline] В пакете не найдено окружение. Инициализирую fallback окружение...
if not exist "%ENV_DIR%" (
  python -m venv "%ENV_DIR%"
)

call "%ENV_DIR%\Scripts\activate.bat"
python -m pip install --upgrade pip >nul
python -m pip install --no-cache-dir -r requirements.txt >nul
set "PYTHON=%ENV_DIR%\Scripts\python.exe"

:run
"%PYTHON%" runserver.py --host %HOST% --port %PORT% --no-reload
