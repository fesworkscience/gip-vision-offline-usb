from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .models import JobRecord


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(raw: str) -> datetime:
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class JobManager:
    def __init__(self, base_dir: Path, input_dir: Path | None = None, output_dir: Path | None = None):
        self.base_dir = base_dir.resolve()
        self.jobs_dir = self.base_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.input_dir = (input_dir or (self.base_dir / "ifc")).resolve()
        self.output_dir = (output_dir or (self.base_dir / "usdz")).resolve()
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._jobs: dict[str, JobRecord] = {}

        retention_days = int(os.getenv("OFFLINE_CONVERTER_RETENTION_DAYS", "7"))
        self.retention = timedelta(days=max(retention_days, 1))

    def load_existing(self) -> int:
        restored = 0
        with self._lock:
            for folder in sorted(self.jobs_dir.iterdir()):
                if not folder.is_dir():
                    continue
                meta = folder / "job.json"
                if not meta.exists():
                    continue
                try:
                    payload = json.loads(meta.read_text(encoding="utf-8"))
                    raw_status = str(payload.get("status", "queued")).strip().lower()
                    known_statuses = {"queued", "running", "cancelling", "done", "failed", "cancelled"}
                    if raw_status not in known_statuses:
                        output_name = payload.get("output_name")
                        output_exists = bool(output_name and (self.output_dir / str(output_name)).exists())
                        raw_status = "done" if output_exists else "queued"

                    record = JobRecord(
                        id=payload["id"],
                        created_at=_parse_datetime(payload["created_at"]),
                        updated_at=_parse_datetime(payload["updated_at"]),
                        status=raw_status,
                        progress=int(payload.get("progress", 0)),
                        stage=payload.get("stage", "queued"),
                        error=payload.get("error"),
                        input_name=payload.get("input_name"),
                        output_name=payload.get("output_name"),
                        work_dir=folder,
                        metadata=payload.get("metadata") or {},
                        cancel_requested=bool(payload.get("cancel_requested", False)),
                    )
                    self._jobs[record.id] = record
                    restored += 1
                except Exception:
                    continue
        return restored

    def list_jobs(self, limit: int = 50) -> list[JobRecord]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda x: x.updated_at, reverse=True)
            return jobs[: max(1, limit)]

    def list_pending_for_resume(self) -> list[JobRecord]:
        """Jobs that should be resumed after service restart."""
        with self._lock:
            items = []
            for record in self._jobs.values():
                status = str(record.status).strip().lower()
                if status in ("queued", "running", "cancelling") and not record.cancel_requested:
                    # After restart, no workers are attached to previous runtime state.
                    # Convert stale "running" to "queued" and re-submit.
                    if status in ("running", "cancelling"):
                        record.status = "queued"
                        record.stage = "queued"
                        record.error = None
                        self._write_meta(record)
                    items.append(record)
            items.sort(key=lambda x: x.updated_at, reverse=False)
            return items

    def create_job(self) -> JobRecord:
        with self._lock:
            job_id = str(uuid4())
            now = _utcnow()
            work_dir = self.jobs_dir / job_id
            work_dir.mkdir(parents=True, exist_ok=False)
            record = JobRecord(
                id=job_id,
                created_at=now,
                updated_at=now,
                work_dir=work_dir,
            )
            self._jobs[job_id] = record
            self._write_meta(record)
            return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> JobRecord:
        with self._lock:
            record = self._jobs[job_id]
            for k, v in kwargs.items():
                setattr(record, k, v)
            record.updated_at = _utcnow()
            self._write_meta(record)
            return record

    def request_cancel(self, job_id: str) -> JobRecord:
        with self._lock:
            record = self._jobs[job_id]
            record.cancel_requested = True
            if record.status == "queued":
                record.status = "cancelled"
                record.stage = "cancelled"
                record.progress = max(record.progress, 100)
                record.error = "Cancelled by user"
            elif record.status == "running":
                record.status = "cancelling"
                record.stage = "cancelling"
                record.error = "Cancellation requested"
            record.updated_at = _utcnow()
            self._write_meta(record)
            return record

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            record = self._jobs.get(job_id)
            return bool(record and record.cancel_requested)

    def set_cancelled(self, job_id: str, reason: str = "Cancelled by user") -> JobRecord:
        return self.update(job_id, status="cancelled", stage="cancelled", error=reason, progress=100)

    def set_failed(self, job_id: str, error: str) -> JobRecord:
        return self.update(job_id, status="failed", stage="failed", error=error, progress=100)

    def set_running(self, job_id: str, stage: str, progress: int) -> JobRecord:
        return self.update(job_id, status="running", stage=stage, progress=max(0, min(progress, 100)))

    def set_done(self, job_id: str, output_name: str, metadata: dict) -> JobRecord:
        return self.update(
            job_id,
            status="done",
            stage="completed",
            progress=100,
            output_name=output_name,
            metadata=metadata,
        )

    @staticmethod
    def _sanitize_filename(name: str, default: str) -> str:
        clean = (name or "").strip().replace("\\", "_").replace("/", "_")
        clean = clean.replace("\n", "_").replace("\r", "_")
        return clean or default

    def input_file_name(self, record: JobRecord) -> str:
        name = self._sanitize_filename(record.input_name or "input.ifc", "input.ifc")
        if not name.lower().endswith(".ifc"):
            name = f"{name}.ifc"
        return f"{record.id}_{name}"

    def output_file_name(self, record: JobRecord) -> str:
        source = self._sanitize_filename(record.input_name or "model.ifc", "model.ifc")
        stem = Path(source).stem or "model"
        return f"{record.id}_{stem}.usdz"

    def input_path(self, record: JobRecord) -> Path:
        return self.input_dir / self.input_file_name(record)

    def glb_path(self, record: JobRecord) -> Path:
        assert record.work_dir is not None
        return record.work_dir / "model.glb"

    def output_path(self, record: JobRecord) -> Path:
        assert record.work_dir is not None
        return record.work_dir / "model.usdz"

    def final_output_path(self, record: JobRecord, output_name: str | None = None) -> Path:
        name = output_name or record.output_name or self.output_file_name(record)
        return self.output_dir / name

    def log_path(self, record: JobRecord) -> Path:
        assert record.work_dir is not None
        return record.work_dir / "job.log"

    def with_log(self, record: JobRecord, message: str) -> None:
        log_path = self.log_path(record)
        timestamp = _utcnow().isoformat()
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")

    def cleanup_expired(self) -> int:
        removed = 0
        cutoff = _utcnow() - self.retention
        with self._lock:
            for job_id, record in list(self._jobs.items()):
                if record.updated_at < cutoff and record.status in ("done", "failed", "cancelled"):
                    self._remove_job_files(record)
                    self._jobs.pop(job_id, None)
                    removed += 1
        return removed

    def _remove_job_files(self, record: JobRecord) -> None:
        if not record.work_dir or not record.work_dir.exists():
            return

        jobs_root = self.jobs_dir.resolve()
        work_dir = record.work_dir.resolve()

        # Safety barrier: cleanup can only delete within config/workspace/jobs/<job_id>.
        if work_dir == jobs_root or jobs_root not in work_dir.parents:
            return

        for p in sorted(work_dir.rglob("*"), reverse=True):
            if p.is_file() or p.is_symlink():
                p.unlink(missing_ok=True)
            elif p.is_dir():
                p.rmdir()
        work_dir.rmdir()

    def _write_meta(self, record: JobRecord) -> None:
        if not record.work_dir:
            return
        meta_path = record.work_dir / "job.json"
        meta_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


ProgressCallback = Callable[[str, int], None]
CancelCheck = Callable[[], bool]
