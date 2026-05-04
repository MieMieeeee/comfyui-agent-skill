from __future__ import annotations

"""Low-risk fallback workflow selection.

This module provides a minimal, conservative selector intended for CLI/default usage when no explicit
workflow has been chosen. Agents should remain the primary decision-maker and explicitly specify
`--workflow` when appropriate.
"""

from collections.abc import Mapping

from comfyui.services.workflow_config import WorkflowConfig


def select_text_to_image_workflow_id(
    prompt: str,
    *,
    registry: Mapping[str, WorkflowConfig],
    default_workflow_id: str,
) -> str:
    prompt_l = (prompt or "").strip().lower()
    if not prompt_l:
        return default_workflow_id

    best_id = default_workflow_id
    best_score = -1

    for workflow_id, cfg in registry.items():
        categories = cfg.intent_categories or ([cfg.capability] if cfg.capability else [])
        if "text_to_image" not in categories:
            continue
        if cfg.output_kind != "image":
            continue
        modes = cfg.input_modes or ["text"]
        if "text" not in modes:
            continue

        keywords = [k for k in (cfg.keywords_any or []) if isinstance(k, str) and k.strip()]
        hits = sum(1 for k in keywords if k.lower() in prompt_l)
        if hits <= 0:
            continue

        score = int(getattr(cfg, "priority", 0) or 0) + hits * 10
        if score > best_score:
            best_score = score
            best_id = workflow_id

    return best_id
