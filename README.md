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
- `app/templates/index.html` — UI
- `workspace/jobs/` — данные задач

## Требования
- Python 3.10+
- `IfcConvert` в PATH **или** рабочий `ifcopenshell.geom` serializer
- Python-пакеты из `requirements.txt`
- `usd-core`/`pxr` должны быть доступны в окружении

## Быстрый запуск
### macOS/Linux
```bash
cd offline_ifc_converter
./run.sh
```

### Windows
```bat
cd offline_ifc_converter
run.bat
```

## Ручной запуск
```bash
cd offline_ifc_converter
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
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
