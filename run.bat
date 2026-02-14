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
set "WHEEL_DIR=.offline_wheels"

if exist "%ENV_DIR%\Scripts\python.exe" (
  "%ENV_DIR%\Scripts\python.exe" -c "import uvicorn" >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON=%ENV_DIR%\Scripts\python.exe"
    goto run
  )
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import uvicorn" >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON=%CD%\.venv\Scripts\python.exe"
    goto run
  )
)

if not "%OFFLINE_STRICT%"=="0" (
  if not exist "%WHEEL_DIR%\*.whl" (
    echo [offline] OFFLINE_STRICT=1 и не найдено рабочее .offline_env.
    echo [offline] Переупакуйте релиз с .offline_wheels или установите OFFLINE_STRICT=0.
    echo [offline] Для локальной разработки используйте OFFLINE_STRICT=0.
    exit /b 1
  )
)

where python >nul 2>&1
if errorlevel 1 (
  echo [offline] Не найден python для bootstrap. Установите Python 3.11+ или скопируйте .offline_env.
  exit /b 1
)

echo [offline] В пакете не найдено окружение. Инициализирую fallback окружение...
if not exist "%ENV_DIR%" (
  python -m venv "%ENV_DIR%"
) else (
  rmdir /s /q "%ENV_DIR%"
  python -m venv "%ENV_DIR%"
)

call "%ENV_DIR%\Scripts\activate.bat"
python -m pip install --upgrade pip >nul
if exist "%WHEEL_DIR%\*.whl" (
  python -m pip install --no-index --find-links "%WHEEL_DIR%" -r requirements.txt >nul
) else if "%OFFLINE_STRICT%"=="0" (
  python -m pip install --no-cache-dir -r requirements.txt >nul
) else (
  echo [offline] OFFLINE_STRICT=1 и не найдено локальных wheels в %WHEEL_DIR%.
  echo [offline] Соберите релиз заново через GitHub Actions, чтобы добавить .offline_wheels.
  exit /b 1
)

set "PYTHON=%ENV_DIR%\Scripts\python.exe"

:run
"%PYTHON%" runserver.py --host %HOST% --port %PORT% --no-reload
