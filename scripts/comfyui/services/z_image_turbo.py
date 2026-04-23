"""Convenience wrapper: execute z_image_turbo workflow with a text prompt.

Thin wrapper around the generic executor + z_image_turbo WorkflowConfig.
"""
from __future__ import annotations

from pathlib import Path

from comfyui.config import SKILL_ROOT
from comfyui.models.result import GenerationResult
from comfyui.services.executor import execute_workflow
from comfyui.services.workflow_config import Z_IMAGE_TURBO


def execute(
    prompt: str,
    server_url: str | None = None,
    results_dir: str | Path | None = None,
    skill_root: Path | None = None,
) -> GenerationResult:
    """Execute z_image_turbo workflow.

    Args:
        prompt: Text prompt for image generation.
        server_url: ComfyUI server URL. Defaults to COMFYUI_URL.
        results_dir: Directory to save output images.
        skill_root: Skill root directory. Defaults to auto-detected SKILL_ROOT.

    Returns:
        GenerationResult with success status and output paths.
    """
    root = skill_root or SKILL_ROOT
    out = Path(results_dir) if results_dir else None

    return execute_workflow(
        config=Z_IMAGE_TURBO,
        prompt=prompt,
        skill_root=root,
        server_url=server_url,
        results_dir=out,
    )
