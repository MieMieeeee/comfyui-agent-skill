"""Generic workflow executor for ComfyUI.

Orchestrates: upload images → load workflow → apply node_mapping params → execute → save images → return result.
Workflow-specific details come from WorkflowConfig.node_mapping.
"""
from __future__ import annotations

import asyncio
import random
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


def _get_default(config: WorkflowConfig, key: str, fallback: int) -> int:
    entry = config.node_mapping.get(key)
    if entry and "default" in entry:
        return entry["default"]
    return fallback


def execute_workflow(
    config: WorkflowConfig,
    prompt: str,
    skill_root: Path,
    server_url: str | None = None,
    results_dir: Path | None = None,
    input_images: dict[str, Path] | None = None,
    width: int | None = None,
    height: int | None = None,
    seed: int | None = None,
) -> GenerationResult:
    """Execute a ComfyUI workflow described by config."""
    # Validate required node_mapping entries
    prompt_entry = config.node_mapping.get("prompt")
    if not prompt_entry:
        return GenerationResult(
            success=False,
            workflow_id=config.workflow_id,
            status="failed",
            error=_err("MAPPING_NOT_FOUND", "Required mapping 'prompt' is missing from workflow config."),
        )

    if not prompt or not prompt.strip():
        return GenerationResult(
            success=False,
            workflow_id=config.workflow_id,
            status="failed",
            error=_err("EMPTY_PROMPT", "Prompt is empty."),
        )

    url = server_url or COMFYUI_URL
    w = width or _get_default(config, "width", 832)
    h = height or _get_default(config, "height", 1280)

    # Resolve seed
    seed_entry = config.node_mapping.get("seed", {})
    actual_seed = seed if seed is not None else random.randint(0, 2**32 - 1)

    out_dir = results_dir or skill_root / "results" / config.workflow_id

    # Load workflow
    workflow_path = config.resolve_workflow_path(skill_root)
    if not workflow_path.exists():
        return GenerationResult(
            success=False,
            workflow_id=config.workflow_id,
            status="failed",
            error=_err("WORKFLOW_FILE_NOT_FOUND", f"Workflow file not found: {workflow_path}"),
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

    # Create API instance early (needed for upload)
    try:
        api = ComfyApiWrapper(url)
    except Exception as e:
        return GenerationResult(
            success=False,
            workflow_id=config.workflow_id,
            status="failed",
            error=_err("SERVER_UNAVAILABLE", f"Cannot connect to ComfyUI: {e}"),
        )

    # Upload input images and bind to nodes
    input_images = input_images or {}
    for role, entry in config.node_mapping.items():
        if entry.get("value_type") != "image":
            continue
        if role not in input_images:
            if entry.get("required"):
                return GenerationResult(
                    success=False,
                    workflow_id=config.workflow_id,
                    status="failed",
                    error=_err("NO_INPUT_IMAGE", f"Required image input '{role}' not provided."),
                )
            continue
        image_path = Path(input_images[role])
        if not image_path.exists():
            return GenerationResult(
                success=False,
                workflow_id=config.workflow_id,
                status="failed",
                error=_err("INPUT_IMAGE_NOT_FOUND", f"Image file not found: {image_path}"),
            )
        try:
            meta = api.upload_image(str(image_path))
        except Exception as e:
            return GenerationResult(
                success=False,
                workflow_id=config.workflow_id,
                status="failed",
                error=_err("IMAGE_UPLOAD_FAILED", f"Failed to upload image '{role}': {e}"),
            )
        img_param = f"{meta['subfolder']}/{meta['name']}" if meta.get("subfolder") else meta["name"]
        wf.set_node_param(entry["node_title"], entry["param"], img_param)

    # Apply node_mapping: set prompt
    if prompt_entry:
        wf.set_node_param(prompt_entry["node_title"], prompt_entry["param"], prompt.strip())

    # Apply node_mapping: set seed
    if seed_entry and seed_entry.get("node_title"):
        wf.set_node_param(seed_entry["node_title"], seed_entry["param"], actual_seed)

    # Apply node_mapping: set dimensions (skip if workflow manages its own size)
    if config.size_strategy != "workflow_managed":
        for dim_key, dim_val in [("width", w), ("height", h)]:
            dim_entry = config.node_mapping.get(dim_key)
            if dim_entry:
                wf.set_node_param(dim_entry["node_title"], dim_entry["param"], dim_val)

    # Execute
    prompt_id = None
    try:
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

    # Retrieve outputs
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
            "seed": actual_seed,
            "prompt_id": prompt_id,
        },
    )
