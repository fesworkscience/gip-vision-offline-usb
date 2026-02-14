# Offline IFC -> USDZ Converter (FastAPI)

Локальный офлайн-сервис для конвертации IFC в USDZ в режиме **Fast** (без Blender):
- `IFC -> GLB` через `IfcConvert`
- fallback: `IFC -> GLB` через Python `IfcOpenShell` (если `IfcConvert` не найден)
- `GLB -> USDZ` через `usd-core/pxr`

## Возможности
- Drag & Drop UI в браузере
- Фоновая обработка задач
- Прогресс по этапам
- Отмена задач
- Скачивание готового USDZ
- Локальные логи по задаче
- Диагностика окружения
- Восстановление списка задач после перезапуска сервиса

## Структура
- `app/main.py` — FastAPI приложение
- `app/job_manager.py` — реестр задач и файловая модель
- `app/converter.py` — fast pipeline + diagnostics
- `app/static/index.html` — UI
- `workspace/jobs/` — данные задач

## Требования
- Python 3.10+
- `IfcConvert` в PATH **или** рабочий `ifcopenshell.geom` serializer
- Python-пакеты из `requirements.txt`
- `usd-core`/`pxr` должны быть доступны в окружении

## Быстрый запуск
### macOS/Linux
```bash
cd gip-vision-offline-usb
chmod +x run.sh run.command
./run.sh
./run.command
```
Если хотите запускать мышкой — дважды кликните `run.command`.

### Windows
```bat
cd gip-vision-offline-usb
run.bat
```

`run.sh`/`run.command` (macOS) и `run.bat` в релизном zip используют `.offline_env`, а если он неработоспособен — соберут локальное окружение из `.offline_wheels` без интернета.

Релизные zip собираются через GitHub Action и включают:
- приложение,
- `requirements.txt`,
- `.offline_env` с установленными зависимостями,
- `.offline_wheels` (локальный кеш wheels для восстановления окружения),
- `.offline_frameworks/Python.framework` (только macOS, для запуска без установленного системного Python),
- `run.sh`/`run.bat`.

Сейчас публикация на теги `v*` делает **ровно 2 файла**:
- `gip-vision-offline-usb-macos-arm64.zip` (Apple Silicon: M1/M2/M3)
- `gip-vision-offline-usb-windows-x64.zip`

На каждом runner GitHub action скачивает платформенно-зависимые зависимости в окружение и упаковывает их в `.offline_env`, а также сохраняет wheels в `.offline_wheels`.  
Для macOS дополнительно упаковывается `Python.framework` в `.offline_frameworks`, чтобы запуск не зависел от Python на машине пользователя.  
По умолчанию запускается `.offline_env`; если он оказался битым, будет восстановлен из `.offline_wheels`.

Для локальной разработки можно временно разрешить bootstrap с интернетом:
```bash
OFFLINE_STRICT=0 ./run.sh
```
или
```bat
set OFFLINE_STRICT=0
run.bat
```

## Ручной запуск
```bash
cd gip-vision-offline-usb
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python runserver.py --host 127.0.0.1 --port 8765
```

Открыть в браузере: `http://127.0.0.1:8765`

## Переменные окружения
- `IFC_CONVERT_PATH` — явный путь к бинарнику `IfcConvert` (опционально)
- `OFFLINE_CONVERTER_MAX_WORKERS` — количество параллельных задач (по умолчанию `1`)
- `OFFLINE_CONVERTER_RETENTION_DAYS` — хранение задач (по умолчанию `7`)
- `OFFLINE_CONVERTER_MAX_UPLOAD_MB` — лимит входного IFC (по умолчанию `1024`)

## API
- `GET /health` — healthcheck
- `GET /api/diagnostics` — диагностика `IfcConvert`, fallback `IfcOpenShell`, `pxr`
- `GET /api/jobs?limit=20` — список последних задач
- `POST /api/jobs` — загрузить IFC и создать задачу
- `GET /api/jobs/{job_id}` — статус задачи
- `POST /api/jobs/{job_id}/cancel` — запросить отмену
- `GET /api/jobs/{job_id}/download` — скачать USDZ
- `GET /api/jobs/{job_id}/logs` — логи

## Примечания
- Отмена задачи кооперативная: запрос обрабатывается между этапами и в цикле IFC-конвертации.
- Автоочистка удаляет старые завершенные/ошибочные/отмененные задачи по retention-политике.
