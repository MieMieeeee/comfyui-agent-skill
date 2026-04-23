from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class WorkflowConfig:
    workflow_id: str
    workflow_file: str
    output_node_title: str
    positive_prompt_node: str
    positive_prompt_param: str = "text"
    negative_prompt_node: str | None = None
    negative_prompt_param: str = "text"
    default_width: int = 832
    default_height: int = 1280

    # Capability-oriented fields
    capability: str = "text_to_image"
    description: str = ""
    input_schema: dict[str, dict[str, Any]] = field(default_factory=lambda: {
        "prompt": {"type": "string", "required": True},
    })
    defaults: dict[str, Any] = field(default_factory=dict)

    def resolve_workflow_path(self, skill_root: Path) -> Path:
        return skill_root / "assets" / "workflows" / self.workflow_file


Z_IMAGE_TURBO = WorkflowConfig(
    workflow_id="z_image_turbo",
    workflow_file="z_image_turbo.json",
    output_node_title="Save Image",
    positive_prompt_node="CLIP Text Encode (Positive Prompt)",
    negative_prompt_node="CLIP Text Encode (Negative Prompt)",
    capability="text_to_image",
    description="Text-to-image generation using Z-Image Turbo model",
    input_schema={
        "prompt": {"type": "string", "required": True},
    },
    defaults={"width": 832, "height": 1280},
)

# Registry: workflow_id → WorkflowConfig. Add new workflows here.
WORKFLOW_REGISTRY: dict[str, WorkflowConfig] = {
    "z_image_turbo": Z_IMAGE_TURBO,
}
