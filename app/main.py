from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import Future
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .converter import get_diagnostics, run_fast_pipeline
from .job_manager import JobManager

APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
WORKSPACE_DIR = PROJECT_DIR / "workspace"

app = FastAPI(title="Offline IFC Converter", version="1.1.0")
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

job_manager = JobManager(base_dir=WORKSPACE_DIR)
max_workers = int(os.getenv("OFFLINE_CONVERTER_MAX_WORKERS", "1"))
executor = ThreadPoolExecutor(max_workers=max(1, max_workers))
_futures_lock = threading.RLock()
_job_futures: dict[str, Future] = {}

upload_limit_mb = int(os.getenv("OFFLINE_CONVERTER_MAX_UPLOAD_MB", "1024"))
upload_limit_bytes = max(1, upload_limit_mb) * 1024 * 1024
_cleanup_stop = threading.Event()
_cleanup_thread: threading.Thread | None = None


def _sanitize_filename(name: str) -> str:
    clean = name.strip().replace("\\", "_").replace("/", "_")
    clean = clean.replace("\n", "_").replace("\r", "_")
    return clean or "model.ifc"


def _cleanup_loop() -> None:
    while not _cleanup_stop.is_set():
        try:
            job_manager.cleanup_expired()
        except Exception:
            pass
        _cleanup_stop.wait(3600)


def _run_job(job_id: str) -> None:
    record = job_manager.get(job_id)
    if not record:
        return

    if record.status == "cancelled":
        return

    try:
        job_manager.set_running(job_id, stage="starting", progress=5)
        job_manager.with_log(record, "Starting fast conversion pipeline")

        def progress_cb(stage: str, progress: int) -> None:
            if job_manager.is_cancel_requested(job_id):
                raise RuntimeError("Cancelled by user")
            job_manager.set_running(job_id, stage=stage, progress=progress)
            rec = job_manager.get(job_id)
            if rec:
                job_manager.with_log(rec, f"Stage={stage}, progress={progress}%")

        input_ifc = job_manager.input_path(record)
        output_glb = job_manager.glb_path(record)
        output_usdz = job_manager.output_path(record)

        started = time.time()
        stats = run_fast_pipeline(
            input_ifc=input_ifc,
            output_glb=output_glb,
            output_usdz=output_usdz,
            progress_cb=progress_cb,
            cancel_check=lambda: job_manager.is_cancel_requested(job_id),
        )

        if job_manager.is_cancel_requested(job_id):
            raise RuntimeError("Cancelled by user")

        out_name = f"{Path(record.input_name or 'model').stem}.usdz"
        final = record.work_dir / out_name
        if final.exists():
            final.unlink()
        output_usdz.rename(final)

        total_seconds = round(time.time() - started, 3)
        stats = dict(stats or {})
        stats["total_seconds"] = total_seconds

        job_manager.with_log(record, f"Completed successfully: {final.name}; total_seconds={total_seconds}")
        job_manager.set_done(job_id, output_name=final.name, metadata=stats)

    except Exception as exc:
        rec = job_manager.get(job_id)
        message = str(exc)
        if rec:
            job_manager.with_log(rec, f"Failed: {message}")
        if "Cancelled by user" in message:
            job_manager.set_cancelled(job_id, reason=message)
        else:
            job_manager.set_failed(job_id, message)
    finally:
        with _futures_lock:
            _job_futures.pop(job_id, None)


def _submit_job(job_id: str) -> None:
    with _futures_lock:
        existing = _job_futures.get(job_id)
        if existing and not existing.done():
            return
        _job_futures[job_id] = executor.submit(_run_job, job_id)


@app.on_event("startup")
def on_startup() -> None:
    restored = job_manager.load_existing()
    removed = job_manager.cleanup_expired()
    resumed = 0
    for record in job_manager.list_pending_for_resume():
        job_manager.with_log(record, "Recovered after restart and queued for processing")
        _submit_job(record.id)
        resumed += 1
    if restored:
        print(f"[offline-converter] restored {restored} existing jobs")
    if removed:
        print(f"[offline-converter] cleaned {removed} expired jobs")
    if resumed:
        print(f"[offline-converter] resumed {resumed} queued/running jobs")

    global _cleanup_thread
    _cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
    _cleanup_thread.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    _cleanup_stop.set()
    if _cleanup_thread and _cleanup_thread.is_alive():
        _cleanup_thread.join(timeout=2)
    executor.shutdown(wait=False, cancel_futures=True)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(path=str(APP_DIR / "static" / "index.html"))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/diagnostics")
def diagnostics() -> JSONResponse:
    return JSONResponse(get_diagnostics())


@app.get("/api/jobs")
def list_jobs(limit: int = 20) -> JSONResponse:
    jobs = [item.to_dict() for item in job_manager.list_jobs(limit=limit)]
    return JSONResponse({"items": jobs})


@app.post("/api/jobs")
async def create_job(file: UploadFile = File(...)) -> JSONResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is missing")

    filename = _sanitize_filename(file.filename)
    ext = Path(filename).suffix.lower()
    if ext != ".ifc":
        raise HTTPException(status_code=400, detail="Only .ifc files are supported")

    record = job_manager.create_job()
    job_manager.update(record.id, input_name=filename)
    input_path = job_manager.input_path(record)

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if len(data) > upload_limit_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Limit is {upload_limit_mb} MB",
        )

    input_path.write_bytes(data)
    job_manager.with_log(record, f"Uploaded {filename}, size={len(data)} bytes")

    _submit_job(record.id)

    return JSONResponse({"job_id": record.id})


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> JSONResponse:
    record = job_manager.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(record.to_dict())


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> JSONResponse:
    record = job_manager.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")

    updated = job_manager.request_cancel(job_id)
    with _futures_lock:
        future = _job_futures.get(job_id)
        # If task did not start yet, cancel immediately and reflect final status.
        if future and future.cancel():
            updated = job_manager.set_cancelled(job_id, reason="Cancelled before start")
            _job_futures.pop(job_id, None)
    job_manager.with_log(updated, "Cancellation requested")
    return JSONResponse(updated.to_dict())


@app.get("/api/jobs/{job_id}/download")
def download_output(job_id: str):
    record = job_manager.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    if record.status != "done" or not record.output_name:
        raise HTTPException(status_code=409, detail="Job is not completed")

    output_path = record.work_dir / record.output_name
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    return FileResponse(path=output_path, filename=record.output_name, media_type="model/vnd.usdz+zip")


@app.get("/api/jobs/{job_id}/logs")
def download_logs(job_id: str):
    record = job_manager.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")

    log_path = job_manager.log_path(record)
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    return FileResponse(path=log_path, filename=f"{job_id}.log", media_type="text/plain")
