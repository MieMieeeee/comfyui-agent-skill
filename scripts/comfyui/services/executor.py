"""Generic workflow executor for ComfyUI.

Orchestrates: upload images → load workflow → apply node_mapping params → execute → save images → return result.
Workflow-specific details come from WorkflowConfig.node_mapping.
"""
from __future__ import annotations

import asyncio
import json
import random
import sys
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import websockets

try:
    from comfy_api_simplified import ComfyApiWrapper, ComfyWorkflowWrapper
except ImportError:
    print(
        "Error: comfy_api_simplified not importable (vendored under scripts/comfy_api_simplified).\n"
        "From the skill root run: pip install -e .\n"
        "Or set PYTHONPATH to the scripts directory.",
        file=sys.stderr,
    )
    sys.exit(1)

from comfyui.config import get_comfyui_url
from comfyui.models.result import GenerationResult
from comfyui.services.workflow_config import WorkflowConfig


def _connection_hint(url: str) -> str:
    return (
        f"Hint / 提示: Make sure ComfyUI is running and the IP/port is correct (current: {url}). "
        f"请确认 ComfyUI 已在目标地址运行，并检查 IP 与端口是否正确（当前: {url}）。"
    )


def _should_add_connection_hint(message: str) -> bool:
    low = message.lower()
    triggers = (
        "timeout",
        "timed out",
        "connection",
        "refused",
        "unreachable",
        "10061",
        "10060",
        "errno 111",
        "errno 10054",
        "failed to establish",
        "getaddrinfo",
        "could not connect",
        "error connecting",
        "newconnectionerror",
        "max retries",
    )
    return any(t in low for t in triggers)


def _enrich_error(message: str, url: str) -> str:
    if not message.strip():
        return _connection_hint(url)
    if _should_add_connection_hint(message):
        return f"{message.rstrip()}\n{_connection_hint(url)}"
    return message


def _simplify_ws_event(prompt_id: str, message: dict[str, Any]) -> dict[str, Any]:
    t = message.get("type", "unknown")
    data = message.get("data") or {}
    if t == "executing" and "node" in data:
        return {"phase": "executing", "prompt_id": prompt_id, "node": data.get("node")}
    if t == "status" and "status" in data:
        ex = (data.get("status") or {}).get("exec_info") or {}
        return {
            "phase": "status",
            "prompt_id": prompt_id,
            "queue_remaining": ex.get("queue_remaining"),
        }
    if t == "progress" and isinstance(data, dict) and "value" in data:
        return {
            "phase": "progress",
            "prompt_id": prompt_id,
            "value": data.get("value"),
            "max": data.get("max"),
        }
    return {"phase": t, "prompt_id": prompt_id, "raw": message}


async def _queue_prompt_and_wait_with_progress(
    api: ComfyApiWrapper,
    prompt: dict,
    on_progress: Callable[[dict[str, Any]], None],
) -> str:
    """Same contract as ComfyApiWrapper.queue_prompt_and_wait, with progress callbacks."""
    client_id = str(uuid.uuid4())
    resp = api.queue_prompt(prompt, client_id)
    prompt_id: str = resp["prompt_id"]
    on_progress({"phase": "queued", "prompt_id": prompt_id})
    async with websockets.connect(uri=api.ws_url.format(client_id)) as websocket:
        while True:
            out = await websocket.recv()
            if not isinstance(out, str):
                continue
            message = json.loads(out)
            if message.get("type") == "crystools.monitor":
                continue
            mtype = message.get("type")
            if mtype in ("status", "executing", "executed", "execution_cached", "progress"):
                on_progress(_simplify_ws_event(prompt_id, message))
            if mtype == "execution_error":
                data = message["data"]
                if data["prompt_id"] == prompt_id:
                    raise RuntimeError("Execution error occurred (ComfyUI reported execution_error).")
            if mtype == "status":
                data = message["data"]
                if data["status"]["exec_info"]["queue_remaining"] == 0:
                    on_progress({"phase": "queue_empty", "prompt_id": prompt_id})
                    return prompt_id
            if mtype == "executing":
                data = message["data"]
                if data["node"] is None and data.get("prompt_id") == prompt_id:
                    on_progress({"phase": "finished", "prompt_id": prompt_id})
                    return prompt_id


def _err(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def node_output_media_list(node_output: dict[str, Any], output_kind: str) -> list[Any]:
    """Resolve ComfyUI history ``outputs[node_id]`` media entries for image / audio / video."""
    kind = (output_kind or "image").strip()
    if kind == "audio":
        return list(node_output.get("audio") or [])
    if kind == "video":
        for key in ("images", "gifs", "videos"):
            lst = node_output.get(key)
            if lst:
                return list(lst)
        return []
    return list(node_output.get("images") or [])


def _entry_is_string_input(entry: dict[str, Any]) -> bool:
    vt = entry.get("value_type")
    if vt == "string":
        return True
    if vt in ("integer", "image"):
        return False
    # Legacy JSON configs may omit value_type for CLIP-style text bindings
    if vt is None and entry.get("param") == "text":
        return True
    return False


def merge_text_inputs(
    config: WorkflowConfig,
    prompt: str,
    text_inputs: dict[str, str] | None,
) -> dict[str, str]:
    """Merge CLI ``prompt`` into mapping key ``prompt`` when present; overlay ``text_inputs``."""
    texts: dict[str, str] = dict(text_inputs or {})
    if prompt.strip() and "prompt" in config.node_mapping:
        texts.setdefault("prompt", prompt.strip())
    return texts


def _missing_string_error(mapping_key: str) -> dict[str, str]:
    codes: dict[str, tuple[str, str]] = {
        "prompt": ("EMPTY_PROMPT", "Prompt is empty."),
        "speech_text": ("EMPTY_SPEECH_TEXT", "Speech text is empty."),
        "instruct": ("EMPTY_INSTRUCT", "Voice instruct is empty."),
    }
    code, msg = codes.get(mapping_key, ("MISSING_INPUT", f"Required input '{mapping_key}' is empty."))
    return _err(code, msg)


def _get_default(config: WorkflowConfig, key: str, fallback: int) -> int:
    entry = config.node_mapping.get(key)
    if entry and "default" in entry:
        return entry["default"]
    return fallback


def _sanitize_prompt_id_for_path(prompt_id: str) -> str:
    return (
        str(prompt_id)
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )


def parse_job_anchor_from_iso(created_at: str | None) -> datetime | None:
    """Parse JobStore ``created_at`` (ISO-8601) for folder naming; ``None`` if invalid."""
    if not created_at or not str(created_at).strip():
        return None
    raw = str(created_at).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone()
    return dt


def job_hierarchy_output_dir(
    skill_root: Path,
    prompt_id: str,
    *,
    anchor: datetime | None = None,
    output_subdir: Path | None = None,
) -> Path:
    """Default artifact directory: ``results/%Y%m%d/%H%M%S_{prompt_id}/`` under ``skill_root``.

    Used for all workflow outputs when no explicit ``results_dir`` is set: raster images,
    audio, and future media types (e.g. video) saved under the same hierarchy.
    """
    anchor = anchor or datetime.now()
    date_part = anchor.strftime("%Y%m%d")
    time_part = anchor.strftime("%H%M%S")
    safe_id = _sanitize_prompt_id_for_path(prompt_id)
    base = skill_root / "results" / date_part / f"{time_part}_{safe_id}"
    if output_subdir is not None:
        base = base / output_subdir
    return base


def execute_workflow(
    config: WorkflowConfig,
    prompt: str,
    skill_root: Path,
    server_url: str | None = None,
    results_dir: Path | None = None,
    output_subdir: Path | None = None,
    input_images: dict[str, Path] | None = None,
    width: int | None = None,
    height: int | None = None,
    seed: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    text_inputs: dict[str, str] | None = None,
) -> GenerationResult:
    """Execute a ComfyUI workflow described by config."""
    workflow_path = config.resolve_workflow_path(skill_root)
    if not workflow_path.exists():
        return GenerationResult(
            success=False,
            workflow_id=config.workflow_id,
            status="failed",
            error=_err("WORKFLOW_FILE_NOT_FOUND", f"Workflow file not found: {workflow_path}"),
        )

    has_string_mapping = any(
        _entry_is_string_input(entry) for entry in config.node_mapping.values()
    )
    if not has_string_mapping:
        return GenerationResult(
            success=False,
            workflow_id=config.workflow_id,
            status="failed",
            error=_err(
                "MAPPING_NOT_FOUND",
                "Workflow config has no string inputs (prompt/speech_text/etc.).",
            ),
        )

    texts = merge_text_inputs(config, prompt, text_inputs)
    for key, entry in config.node_mapping.items():
        if not _entry_is_string_input(entry) or not entry.get("required"):
            continue
        if not texts.get(key, "").strip():
            return GenerationResult(
                success=False,
                workflow_id=config.workflow_id,
                status="failed",
                error=_missing_string_error(key),
            )

    url = server_url or get_comfyui_url()
    dim_w_entry = config.node_mapping.get("width")
    dim_h_entry = config.node_mapping.get("height")
    if config.size_strategy != "workflow_managed" and dim_w_entry and dim_h_entry:
        w = width if width is not None else _get_default(config, "width", 832)
        h = height if height is not None else _get_default(config, "height", 1280)
    else:
        w = width
        h = height

    # Resolve seed
    seed_entry = config.node_mapping.get("seed", {})
    actual_seed = seed if seed is not None else random.randint(0, 2**32 - 1)

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
        msg = _enrich_error(str(e), url)
        return GenerationResult(
            success=False,
            workflow_id=config.workflow_id,
            status="failed",
            error=_err("SERVER_UNAVAILABLE", f"Cannot connect to ComfyUI: {msg}"),
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

    # Apply node_mapping: all string inputs (prompt, speech_text, instruct, negative_prompt, ...)
    for key, entry in config.node_mapping.items():
        if not _entry_is_string_input(entry):
            continue
        val = texts.get(key)
        if val is None or not str(val).strip():
            continue
        wf.set_node_param(entry["node_title"], entry["param"], str(val).strip())

    # Apply node_mapping: set seed
    if seed_entry and seed_entry.get("node_title"):
        wf.set_node_param(seed_entry["node_title"], seed_entry["param"], actual_seed)

    # Apply node_mapping: set dimensions (skip if workflow manages its own size or has no dim mapping)
    if config.size_strategy != "workflow_managed" and dim_w_entry and dim_h_entry:
        for dim_key, dim_val in [("width", w), ("height", h)]:
            dim_entry = config.node_mapping.get(dim_key)
            if dim_entry:
                wf.set_node_param(dim_entry["node_title"], dim_entry["param"], dim_val)

    # Execute
    prompt_id = None
    try:
        loop = asyncio.new_event_loop()
        try:
            if progress_callback is None:
                prompt_id = loop.run_until_complete(api.queue_prompt_and_wait(wf))
            else:
                prompt_id = loop.run_until_complete(
                    _queue_prompt_and_wait_with_progress(api, wf, progress_callback)
                )
        finally:
            loop.close()
    except Exception as e:
        err_text = str(e)
        if _should_add_connection_hint(err_text):
            err_text = _enrich_error(err_text, url)
        return GenerationResult(
            success=False,
            workflow_id=config.workflow_id,
            status="failed",
            error=_err("EXECUTION_FAILED", f"Workflow execution failed: {err_text}"),
            job_id=prompt_id,
        )

    # Retrieve outputs (images or audio)
    output_kind = getattr(config, "output_kind", "image") or "image"
    try:
        output_node_id = wf.get_node_id(config.output_node_title)
        history = api.get_history(prompt_id) if prompt_id else {}
        history_entry = history.get(prompt_id, {})
        comfyui_outputs = history_entry.get("outputs", {})
        node_output = comfyui_outputs.get(output_node_id, {})
        media_info = node_output_media_list(node_output, output_kind)
    except Exception:
        media_info = []

    if not media_info:
        if output_kind == "audio":
            msg = "Workflow completed but produced no audio."
        elif output_kind == "video":
            msg = "Workflow completed but produced no video output."
        else:
            msg = "Workflow completed but produced no images."
        return GenerationResult(
            success=False,
            workflow_id=config.workflow_id,
            status="failed",
            error=_err("NO_OUTPUT", msg),
            job_id=prompt_id,
        )

    if results_dir is not None:
        out_dir = Path(results_dir)
    else:
        out_dir = job_hierarchy_output_dir(
            skill_root,
            str(prompt_id),
            anchor=datetime.now(),
            output_subdir=output_subdir,
        )

    # Save files (images, audio, or other media via same /view fetch)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for item in media_info:
        filename = item["filename"]
        subfolder = item.get("subfolder", "")
        folder_type = item.get("type", "output")
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
            if output_kind == "audio":
                label = "audio"
            elif output_kind == "video":
                label = "video"
            else:
                label = "image"
            return GenerationResult(
                success=False,
                workflow_id=config.workflow_id,
                status="failed",
                error=_err("SAVE_FAILED", f"Failed to save {label} {filename}: {e}"),
                job_id=prompt_id,
            )

    meta: dict[str, Any] = {
        "seed": actual_seed,
        "prompt_id": prompt_id,
    }
    if prompt.strip():
        meta["prompt"] = prompt
    for k in ("speech_text", "instruct"):
        if texts.get(k):
            meta[k] = texts[k]
    if config.size_strategy != "workflow_managed" and dim_w_entry and dim_h_entry:
        meta["width"] = w
        meta["height"] = h

    return GenerationResult(
        success=True,
        workflow_id=config.workflow_id,
        status="completed",
        outputs=outputs,
        job_id=prompt_id,
        metadata=meta,
    )
