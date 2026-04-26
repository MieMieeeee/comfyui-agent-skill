from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Raised when a workflow config file is invalid."""


@dataclass
class WorkflowConfig:
    workflow_id: str
    workflow_file: str
    output_node_title: str
    node_mapping: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Capability-oriented fields
    capability: str = "text_to_image"
    description: str = ""
    size_strategy: str = ""  # "workflow_managed" = dims from workflow, not skill

    def resolve_workflow_path(self, skill_root: Path) -> Path:
        return skill_root / "assets" / "workflows" / self.workflow_file

    def to_json(self) -> str:
        return json.dumps({
            "workflow_id": self.workflow_id,
            "workflow_file": self.workflow_file,
            "output_node_title": self.output_node_title,
            "capability": self.capability,
            "description": self.description,
            "size_strategy": self.size_strategy,
            "node_mapping": self.node_mapping,
        }, ensure_ascii=False, indent=2)

    @classmethod
    def from_json_file(cls, path: Path) -> WorkflowConfig:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as e:
            raise ConfigError(f"Cannot read config file {path}: {e}") from e

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config file {path}: {e}") from e

        for field_name in ("workflow_id", "workflow_file", "output_node_title"):
            if field_name not in data:
                raise ConfigError(f"Missing required field '{field_name}' in {path}")

        return cls(
            workflow_id=data["workflow_id"],
            workflow_file=data["workflow_file"],
            output_node_title=data["output_node_title"],
            node_mapping=data.get("node_mapping", {}),
            capability=data.get("capability", "text_to_image"),
            description=data.get("description", ""),
            size_strategy=data.get("size_strategy", ""),
        )


def load_configs_from_dir(workflows_dir: Path) -> dict[str, WorkflowConfig]:
    registry: dict[str, WorkflowConfig] = {}
    for config_file in sorted(workflows_dir.glob("*.config.json")):
        try:
            cfg = WorkflowConfig.from_json_file(config_file)
        except ConfigError:
            raise
        registry[cfg.workflow_id] = cfg
    return registry


# Built-in fallback (used when JSON configs aren't available)
Z_IMAGE_TURBO = WorkflowConfig(
    workflow_id="z_image_turbo",
    workflow_file="z_image_turbo.json",
    output_node_title="Save Image",
    node_mapping={
        "prompt": {
            "node_title": "CLIP Text Encode (Positive Prompt)",
            "param": "text",
            "value_type": "string",
            "required": True,
        },
        "negative_prompt": {
            "node_title": "CLIP Text Encode (Negative Prompt)",
            "param": "text",
            "value_type": "string",
        },
        "seed": {
            "node_title": "KSampler",
            "param": "seed",
            "value_type": "integer",
            "auto_random": True,
        },
        "width": {
            "node_title": "EmptySD3LatentImage",
            "param": "width",
            "value_type": "integer",
            "default": 832,
        },
        "height": {
            "node_title": "EmptySD3LatentImage",
            "param": "height",
            "value_type": "integer",
            "default": 1280,
        },
    },
    capability="text_to_image",
    description="Text-to-image generation using Z-Image Turbo model",
)

# Registry: workflow_id → WorkflowConfig. Prefer JSON configs; fall back to built-in.
def _build_registry() -> dict[str, WorkflowConfig]:
    registry: dict[str, WorkflowConfig] = {}
    # Resolve skill root: workflow_config.py -> services/ -> comfyui/ -> scripts/ -> skill_root/
    skill_root = Path(__file__).resolve().parent.parent.parent.parent
    workflows_dir = skill_root / "assets" / "workflows"
    if workflows_dir.is_dir():
        registry.update(load_configs_from_dir(workflows_dir))
    # Built-in fallbacks (only if JSON config didn't load them)
    for wid, cfg in [("z_image_turbo", Z_IMAGE_TURBO)]:
        if wid not in registry:
            registry[wid] = cfg
    return registry


WORKFLOW_REGISTRY: dict[str, WorkflowConfig] = _build_registry()
