from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class JobRecord:
    id: str
    created_at: datetime
    updated_at: datetime
    status: str = "queued"  # queued | running | cancelling | done | failed | cancelled
    progress: int = 0
    stage: str = "queued"
    error: str | None = None
    input_name: str | None = None
    output_name: str | None = None
    work_dir: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    cancel_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status,
            "progress": self.progress,
            "stage": self.stage,
            "error": self.error,
            "input_name": self.input_name,
            "output_name": self.output_name,
            "metadata": self.metadata,
            "cancel_requested": self.cancel_requested,
        }
