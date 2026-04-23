from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GenerationResult:
    success: bool
    workflow_id: str
    status: str  # "completed" | "failed" | "server_unavailable"
    outputs: list[dict[str, Any]] = field(default_factory=list)
    error: dict[str, str] | None = None  # {"code": "ERROR_CODE", "message": "..."}
    job_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "workflow_id": self.workflow_id,
            "status": self.status,
            "outputs": self.outputs,
            "error": self.error,
            "job_id": self.job_id,
            "metadata": self.metadata,
        }
