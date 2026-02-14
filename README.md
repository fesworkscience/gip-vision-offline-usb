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
./run.sh
```

### Windows
```bat
cd gip-vision-offline-usb
run.bat
```

`run.sh`/`run.bat` в релизном zip используют `.offline_env` и запускаются без `pip install`.

Релизные zip собираются через GitHub Action и включают:
- приложение,
- `requirements.txt`,
- готовый `.offline_env` c установленными зависимостями,
- `run.sh`/`run.bat`.

Сейчас публикация на теги `v*` делает **ровно 2 файла**:
- `gip-vision-offline-usb-macos-silicon.zip` (Apple Silicon: M1/M2/M3)
- `gip-vision-offline-usb-windows-x64.zip`

На каждом runner GitHub action скачивает платформенно-зависимые зависимости в соответствующее окружение и упаковывает их в `.offline_env`, поэтому после распаковки пользователь запускает только `run.sh` или `run.bat`. Скрипт по умолчанию (`OFFLINE_STRICT=1`) требует наличие `.offline_env` и не делает `pip install`.

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
