"""Generic workflow executor for ComfyUI.

Orchestrates: load workflow → set prompt → execute → save images → return result.
Workflow-specific details (node titles, file paths) come from WorkflowConfig.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

try:
    from comfy_api_simplified import ComfyApiWrapper, ComfyWorkflowWrapper
except ImportError:
    print(
        "Error: comfy_api_simplified not installed.\n"
        "Install with: pip install git+https://github.com/MieMieeeee/run_comfyui_workflow.git",
        file=sys.stderr,
    )
    sys.exit(1)

from comfyui.config import COMFYUI_URL
from comfyui.models.result import GenerationResult
from comfyui.services.workflow_config import WorkflowConfig


def _err(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def execute_workflow(
    config: WorkflowConfig,
    prompt: str,
    skill_root: Path,
    server_url: str | None = None,
    results_dir: Path | None = None,
    width: int | None = None,
    height: int | None = None,
) -> GenerationResult:
    """Execute a ComfyUI workflow described by config."""
    # Validate prompt
    if not prompt or not prompt.strip():
        return GenerationResult(
            success=False,
            workflow_id=config.workflow_id,
            status="failed",
            error=_err("EMPTY_PROMPT", "Prompt is empty."),
        )

    url = server_url or COMFYUI_URL
    w = width or config.default_width
    h = height or config.default_height
    out_dir = results_dir or skill_root / "results" / config.workflow_id

    # Load workflow
    workflow_path = config.resolve_workflow_path(skill_root)
    if not workflow_path.exists():
        return GenerationResult(
            success=False,
            workflow_id=config.workflow_id,
            status="failed",
            error=_err("WORKFLOW_NOT_FOUND", f"Workflow file not found: {workflow_path}"),
        )

    try:
        wf = ComfyWorkflowWrapper(str(workflow_path))
    except Exception as e:
        return GenerationResult(
            success=False,
            workflow_id=config.workflow_id,
            status="failed",
            error=_err("WORKFLOW_LOAD_FAILED", f"Failed to load workflow: {e}"),
        )

    # Set prompt
    wf.set_node_param(config.positive_prompt_node, config.positive_prompt_param, prompt.strip())

    # Execute — queue_prompt_and_wait is async, run via asyncio
    prompt_id = None
    try:
        api = ComfyApiWrapper(url)
        loop = asyncio.new_event_loop()
        try:
            prompt_id = loop.run_until_complete(api.queue_prompt_and_wait(wf))
        finally:
            loop.close()
    except Exception as e:
        return GenerationResult(
            success=False,
            workflow_id=config.workflow_id,
            status="failed",
            error=_err("EXECUTION_FAILED", f"Workflow execution failed: {e}"),
            job_id=prompt_id,
        )

    # Retrieve outputs from history
    try:
        output_node_id = wf.get_node_id(config.output_node_title)
        history = api.get_history(prompt_id) if prompt_id else {}
        history_entry = history.get(prompt_id, {})
        comfyui_outputs = history_entry.get("outputs", {})
        node_output = comfyui_outputs.get(output_node_id, {})
        images_info = node_output.get("images", [])
    except Exception:
        images_info = []

    if not images_info:
        return GenerationResult(
            success=False,
            workflow_id=config.workflow_id,
            status="failed",
            error=_err("NO_OUTPUT", "Workflow completed but produced no images."),
            job_id=prompt_id,
        )

    # Save images
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for img_info in images_info:
        filename = img_info["filename"]
        subfolder = img_info.get("subfolder", "")
        folder_type = img_info.get("type", "output")
        try:
            data = api.get_image(filename, subfolder, folder_type)
            out_path = out_dir / filename
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(data)
            outputs.append({
                "path": str(out_path),
                "filename": filename,
                "size_bytes": len(data),
            })
        except Exception as e:
            return GenerationResult(
                success=False,
                workflow_id=config.workflow_id,
                status="failed",
                error=_err("SAVE_FAILED", f"Failed to save image {filename}: {e}"),
                job_id=prompt_id,
            )

    return GenerationResult(
        success=True,
        workflow_id=config.workflow_id,
        status="completed",
        outputs=outputs,
        job_id=prompt_id,
        metadata={
            "prompt": prompt,
            "width": w,
            "height": h,
            "prompt_id": prompt_id,
        },
    )
