"""Workflow submission layer: validates params, uploads images, submits to ComfyUI, stores jobs."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from comfyui.services.executor import _entry_is_string_input, merge_text_inputs, _missing_string_error
from comfyui.services.job_store import JobStore
from comfyui.services.workflow_config import WORKFLOW_REGISTRY, WorkflowConfig

try:
    from comfy_api_simplified import ComfyApiWrapper, ComfyWorkflowWrapper
except ImportError:
    ComfyApiWrapper = None  # type: ignore
    ComfyWorkflowWrapper = None  # type: ignore


def _err(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _get_default(config: WorkflowConfig, key: str, fallback: int) -> int:
    entry = config.node_mapping.get(key)
    if entry and "default" in entry:
        return entry["default"]
    return fallback


def submit_workflow(
    workflow_id: str,
    prompt: str,
    skill_root: Path,
    job_store_path: Path | None = None,
    server_url: str = "http://127.0.0.1:8188",
    input_images: dict[str, Path] | None = None,
    width: int | None = None,
    height: int | None = None,
    seed: int | None = None,
    count: int = 1,
    text_inputs: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Validate → upload images → submit to ComfyUI → store in JobStore → return job_ids.

    Returns:
        {"submitted": True, "job_ids": [...]} on success
        {"submitted": False, "error": {...}} on validation/server failure
    """
    config = WORKFLOW_REGISTRY.get(workflow_id)
    if config is None:
        return {"submitted": False, "error": _err("WORKFLOW_NOT_REGISTERED", f"Workflow '{workflow_id}' is not registered.")}

    has_string_mapping = any(
        _entry_is_string_input(entry) for entry in config.node_mapping.values()
    )
    if not has_string_mapping:
        return {"submitted": False, "error": _err("MAPPING_NOT_FOUND", "Workflow config has no string inputs.")}

    texts = merge_text_inputs(config, prompt, text_inputs)
    for key, entry in config.node_mapping.items():
        if not _entry_is_string_input(entry) or not entry.get("required"):
            continue
        if not texts.get(key, "").strip():
            return {"submitted": False, "error": _missing_string_error(key)}

    if job_store_path is None:
        job_store_path = skill_root / "jobs.db"
    job_store_path = Path(job_store_path)
    store = JobStore(job_store_path)

    workflow_path = config.resolve_workflow_path(skill_root)
    if not workflow_path.exists():
        return {"submitted": False, "error": _err("WORKFLOW_FILE_NOT_FOUND", f"Workflow file not found: {workflow_path}")}

    try:
        api = ComfyApiWrapper(server_url)
    except Exception as e:
        return {"submitted": False, "error": _err("SERVER_UNAVAILABLE", f"Cannot connect to ComfyUI: {e}")}

    job_ids: list[str] = []

    for _i in range(count):
        seed_entry = config.node_mapping.get("seed", {})
        actual_seed = seed if seed is not None else random.randint(0, 2**32 - 1)

        try:
            wf = ComfyWorkflowWrapper(str(workflow_path))
        except Exception as e:
            return {"submitted": False, "error": _err("WORKFLOW_LOAD_FAILED", f"Failed to load workflow: {e}")}

        input_images = input_images or {}
        for role, entry in config.node_mapping.items():
            if entry.get("value_type") != "image":
                continue
            if role not in input_images:
                if entry.get("required"):
                    return {"submitted": False, "error": _err("NO_INPUT_IMAGE", f"Required image input '{role}' not provided.")}
                continue
            image_path = Path(input_images[role])
            if not image_path.exists():
                return {"submitted": False, "error": _err("INPUT_IMAGE_NOT_FOUND", f"Image file not found: {image_path}")}
            try:
                meta = api.upload_image(str(image_path))
            except Exception as e:
                return {"submitted": False, "error": _err("IMAGE_UPLOAD_FAILED", f"Failed to upload image '{role}': {e}")}
            img_param = f"{meta['subfolder']}/{meta['name']}" if meta.get("subfolder") else meta["name"]
            wf.set_node_param(entry["node_title"], entry["param"], img_param)

        for key, entry in config.node_mapping.items():
            if not _entry_is_string_input(entry):
                continue
            val = texts.get(key)
            if val is None or not str(val).strip():
                continue
            wf.set_node_param(entry["node_title"], entry["param"], str(val).strip())

        if seed_entry and seed_entry.get("node_title"):
            wf.set_node_param(seed_entry["node_title"], seed_entry["param"], actual_seed)

        if config.size_strategy != "workflow_managed":
            w = width or _get_default(config, "width", 832)
            h = height or _get_default(config, "height", 1280)
            for dim_key, dim_val in [("width", w), ("height", h)]:
                dim_entry = config.node_mapping.get(dim_key)
                if dim_entry:
                    wf.set_node_param(dim_entry["node_title"], dim_entry["param"], dim_val)
        else:
            w, h = None, None

        try:
            resp = api.queue_prompt(wf)
            job_id: str = resp["prompt_id"]
        except Exception as e:
            return {"submitted": False, "error": _err("SUBMISSION_FAILED", f"Failed to submit workflow: {e}")}

        if getattr(config, "output_kind", "image") == "audio":
            prompt_store = json.dumps(texts, ensure_ascii=False)
        else:
            prompt_store = texts.get("prompt", prompt.strip())

        store.save_job(
            job_id=job_id,
            workflow_id=workflow_id,
            prompt=prompt_store,
            input_images=json.dumps({k: str(v) for k, v in input_images.items()}) if input_images else None,
            width=w,
            height=h,
            server_url=server_url,
            status="submitted",
            seed=actual_seed,
            count=count,
        )

        job_ids.append(job_id)

    return {"submitted": True, "job_ids": job_ids}
