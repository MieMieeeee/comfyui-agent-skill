from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from comfyui.config import get_custom_workflows_dir, get_workflows_dir
from comfyui.services.errors import ConfigError

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
    output_kind: str = "image"  # "image" | "audio" | "video" — selects history output keys (see executor.node_output_media_list)
    intent_categories: list[str] = field(default_factory=list)
    input_modes: list[str] = field(default_factory=list)
    priority: int = 0
    keywords_any: list[str] = field(default_factory=list)
    selection_guidance: dict[str, Any] = field(default_factory=dict)
    # Optional: human/Agent reference only unless tooling consumes them
    resolution_presets: dict[str, Any] = field(default_factory=dict)
    default_resolution: str = ""
    config_path: Path | None = field(default=None, repr=False, compare=False)

    def resolve_workflow_path(self, workflows_dir: Path) -> Path:
        p = Path(self.workflow_file)
        if p.is_absolute():
            return p
        primary = workflows_dir / self.workflow_file
        if primary.exists():
            return primary
        if self.config_path is not None:
            candidate = self.config_path.parent / self.workflow_file
            if candidate.exists():
                return candidate
        return get_custom_workflows_dir() / self.workflow_file

    def to_json(self) -> str:
        payload = {
            "workflow_id": self.workflow_id,
            "workflow_file": self.workflow_file,
            "output_node_title": self.output_node_title,
            "capability": self.capability,
            "description": self.description,
            "size_strategy": self.size_strategy,
            "output_kind": self.output_kind,
            "intent_categories": self.intent_categories,
            "input_modes": self.input_modes,
            "priority": self.priority,
            "keywords_any": self.keywords_any,
            "selection_guidance": self.selection_guidance,
            "node_mapping": self.node_mapping,
        }
        if self.resolution_presets:
            payload["resolution_presets"] = self.resolution_presets
        if self.default_resolution:
            payload["default_resolution"] = self.default_resolution
        return json.dumps(payload, ensure_ascii=False, indent=2)

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
            output_kind=data.get("output_kind", "image"),
            intent_categories=data.get("intent_categories") or [],
            input_modes=data.get("input_modes") or [],
            priority=int(data.get("priority") or 0),
            keywords_any=data.get("keywords_any") or [],
            selection_guidance=data.get("selection_guidance") or {},
            resolution_presets=data.get("resolution_presets") or {},
            default_resolution=data.get("default_resolution") or "",
            config_path=path,
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


def _iter_user_workflow_config_files(custom_dir: Path) -> list[Path]:
    files: list[Path] = []
    files.extend(sorted(custom_dir.glob("*.config.json")))
    for p in sorted(custom_dir.glob("*/workflow.config.json")):
        files.append(p)
    return files


def load_user_configs_from_dir(
    custom_dir: Path,
    *,
    builtin_ids: set[str],
) -> tuple[dict[str, WorkflowConfig], list[dict[str, Any]]]:
    registry: dict[str, WorkflowConfig] = {}
    errors: list[dict[str, Any]] = []
    try:
        config_files = _iter_user_workflow_config_files(custom_dir)
    except OSError as e:
        errors.append(
            {
                "code": "USER_WORKFLOW_REGISTRY_UNAVAILABLE",
                "message": f"Cannot scan user workflow registry directory: {e}",
                "path": str(custom_dir),
            }
        )
        return registry, errors

    for config_file in config_files:
        try:
            cfg = WorkflowConfig.from_json_file(config_file)
        except ConfigError as e:
            errors.append(
                {
                    "code": "USER_WORKFLOW_CONFIG_INVALID",
                    "message": str(e),
                    "path": str(config_file),
                }
            )
            continue
        if cfg.workflow_id in builtin_ids:
            errors.append(
                {
                    "code": "USER_WORKFLOW_ID_CONFLICTS_WITH_BUILTIN",
                    "message": f"User workflow_id '{cfg.workflow_id}' conflicts with a built-in workflow. Rename it to activate.",
                    "path": str(config_file),
                    "workflow_id": cfg.workflow_id,
                }
            )
            continue
        if cfg.workflow_id in registry:
            errors.append(
                {
                    "code": "USER_WORKFLOW_ID_DUPLICATE",
                    "message": f"Duplicate user workflow_id '{cfg.workflow_id}' found. Only the first one is loaded.",
                    "path": str(config_file),
                    "workflow_id": cfg.workflow_id,
                }
            )
            continue
        registry[cfg.workflow_id] = cfg
    return registry, errors


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
    output_kind="image",
    intent_categories=["text_to_image"],
    input_modes=["text"],
    priority=50,
    keywords_any=[],
    selection_guidance={
        "best_for": [
            "general-purpose text-to-image requests",
            "photoreal image generation without special text rendering requirements",
        ],
        "avoid_for": [
            "poster-style requests",
            "images requiring prominent embedded text",
        ],
        "agent_hint": "Use this as the default fallback T2I workflow when no more specialized registered workflow is a stronger match.",
    },
)

WORKFLOW_REGISTRY_ERRORS: list[dict[str, Any]] = []

# Registry: workflow_id → WorkflowConfig. Prefer JSON configs; fall back to built-in.
def _build_registry() -> dict[str, WorkflowConfig]:
    registry: dict[str, WorkflowConfig] = {}
    workflows_dir = get_workflows_dir()
    if workflows_dir.is_dir():
        registry.update(load_configs_from_dir(workflows_dir))

    builtin_ids = set(registry.keys())
    custom_dir = get_custom_workflows_dir()
    if custom_dir.is_dir():
        user_registry, errors = load_user_configs_from_dir(custom_dir, builtin_ids=builtin_ids)
        registry.update(user_registry)
        WORKFLOW_REGISTRY_ERRORS.extend(errors)
    # Built-in fallbacks (only if JSON config didn't load them)
    for wid, cfg in [("z_image_turbo", Z_IMAGE_TURBO)]:
        if wid not in registry:
            registry[wid] = cfg
    return registry


WORKFLOW_REGISTRY: dict[str, WorkflowConfig] = _build_registry()
