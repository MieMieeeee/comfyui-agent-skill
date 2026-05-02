"""Async job polling layer: WS priority + HTTP fallback, single snapshot semantics."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from comfy_api_simplified import ComfyApiWrapper, ComfyWorkflowWrapper
except ImportError:
    ComfyApiWrapper = None  # type: ignore
    ComfyWorkflowWrapper = None  # type: ignore

from comfyui.config import SKILL_ROOT
from comfyui.services.executor import (
    job_hierarchy_output_dir,
    node_output_media_list,
    parse_job_anchor_from_iso,
)
from comfyui.services.job_store import JobStore
from comfyui.services.workflow_config import WORKFLOW_REGISTRY, WorkflowConfig


def _err(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _materialize_outputs(
    api: Any,
    config: WorkflowConfig,
    skill_root: Path,
    history_entry: dict,
    results_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Download images from ComfyUI into ``results_dir`` (same shape as executor)."""
    if ComfyWorkflowWrapper is None:
        return [], history_entry.get("outputs", {})

    comfyui_outputs = history_entry.get("outputs", {})
    workflow_path = config.resolve_workflow_path(skill_root)
    output_node_id: str | None = None
    if workflow_path.exists():
        try:
            wf = ComfyWorkflowWrapper(str(workflow_path))
            output_node_id = wf.get_node_id(config.output_node_title)
        except Exception:
            output_node_id = None

    output_kind = getattr(config, "output_kind", "image") or "image"
    if output_node_id is None:
        for nid, node_data in comfyui_outputs.items():
            if output_kind == "audio" and node_data.get("audio"):
                output_node_id = nid
                break
            if output_kind == "video" and any(
                node_data.get(k) for k in ("images", "gifs", "videos")
            ):
                output_node_id = nid
                break
            if output_kind == "image" and node_data.get("images"):
                output_node_id = nid
                break

    if output_node_id is None:
        return [], comfyui_outputs

    node_output = comfyui_outputs.get(output_node_id, {})
    media_info = node_output_media_list(node_output, output_kind)

    results_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, Any]] = []
    for item in media_info:
        filename = item["filename"]
        subfolder = item.get("subfolder", "")
        folder_type = item.get("type", "output")
        try:
            data = api.get_image(filename, subfolder, folder_type)
            out_path = results_dir / filename
            out_path.write_bytes(data)
            artifacts.append({
                "path": str(out_path.resolve()),
                "filename": filename,
                "size_bytes": len(data),
            })
        except Exception:
            continue

    return artifacts, comfyui_outputs


async def _poll_ws_once(job_id: str, api_url: str, timeout: float = 3.0) -> dict[str, Any] | None:
    """
    Attempt to read WS messages for this prompt_id within ``timeout``.
    Returns progress dict or None on timeout/error.
    """
    import uuid

    import websockets

    if ComfyApiWrapper is None:
        return None

    try:
        client_id = str(uuid.uuid4())
        api = ComfyApiWrapper(api_url)
        ws_url = api.ws_url.format(client_id)

        async with websockets.connect(ws_url, close_timeout=timeout) as ws:
            async with asyncio.timeout(timeout):
                while True:
                    raw = await ws.recv()
                    if not isinstance(raw, str):
                        continue
                    msg = json.loads(raw)
                    if msg.get("type") == "crystools.monitor":
                        continue
                    data = msg.get("data") or {}
                    if msg.get("type") == "executing" and data.get("node") is not None:
                        pid = data.get("prompt_id")
                        if pid == job_id:
                            return {"phase": "executing", "node": data.get("node"), "prompt_id": job_id}
                    if msg.get("type") == "executing" and data.get("node") is None:
                        pid = data.get("prompt_id")
                        if pid == job_id:
                            return {"phase": "finished", "prompt_id": job_id}
    except Exception:
        pass
    return None


def _sync_ws_poll(job_id: str, api_url: str, timeout: float = 3.0) -> dict[str, Any] | None:
    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_poll_ws_once(job_id, api_url, timeout))
        finally:
            loop.close()
    except Exception:
        return None


def poll_job(
    job_id: str,
    store: JobStore,
    poll_server_url: str | None = None,
    *,
    skill_root: Path | None = None,
    results_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Single-shot poll: read job from store, check ComfyUI status, update store, return snapshot.

    WS is tried first for real-time progress (phase/node). HTTP /history/{job_id} is the
    authoritative result source — presence of outputs means completed (after save), error fields mean failed.

    ``poll_server_url``: if set, use this URL for this poll only; if ``None``, use the URL stored on the job.
    """
    job = store.get_job(job_id)
    if job is None:
        return {
            "success": False,
            "workflow_id": "unknown",
            "status": "unknown",
            "outputs": [],
            "job_id": job_id,
            "error": _err("JOB_NOT_FOUND", f"Job '{job_id}' not found in store."),
            "metadata": {},
        }

    def _extract_text_metadata(raw_prompt: str, raw_text_inputs: str | None) -> dict[str, Any]:
        md: dict[str, Any] = {}
        if raw_prompt and str(raw_prompt).strip():
            md["prompt"] = str(raw_prompt).strip()
        if raw_text_inputs and str(raw_text_inputs).strip():
            try:
                obj = json.loads(str(raw_text_inputs))
            except Exception:
                obj = None
            if isinstance(obj, dict):
                for k in ("speech_text", "instruct"):
                    v = obj.get(k)
                    if isinstance(v, str) and v.strip():
                        md[k] = v
        return md

    def _base_metadata() -> dict[str, Any]:
        md = _extract_text_metadata(job.get("prompt") or "", job.get("text_inputs"))
        if job.get("seed") is not None:
            md["seed"] = job["seed"]
        if job.get("width") is not None:
            md["width"] = job["width"]
        if job.get("height") is not None:
            md["height"] = job["height"]
        return md

    def _snapshot(
        *,
        success: bool,
        status: str,
        outputs: list[dict[str, Any]] | None,
        error: dict[str, str] | None,
        metadata: dict[str, Any] | None = None,
        phase: str | None = None,
        node: str | None = None,
        completed_at: str | None = None,
        transient_error: bool | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "success": success,
            "workflow_id": job["workflow_id"],
            "status": status,
            "outputs": outputs or [],
            "job_id": job_id,
            "error": error,
            "metadata": metadata or {},
        }
        if transient_error is True:
            payload["transient_error"] = True
        if phase is not None:
            payload["phase"] = phase
        if node is not None:
            payload["node"] = node
        if completed_at is not None:
            payload["completed_at"] = completed_at
        return payload

    url = poll_server_url if poll_server_url is not None else job["server_url"]

    root = skill_root if skill_root is not None else SKILL_ROOT

    try:
        api = ComfyApiWrapper(url)
    except Exception as e:
        err_obj = _err("SERVER_UNAVAILABLE", str(e))
        store.update_job(
            job_id,
            last_polled_at=_now_iso(),
            last_error=json.dumps(err_obj),
        )
        return _snapshot(
            success=False,
            status=job["status"],
            outputs=[],
            error=err_obj,
            metadata=_base_metadata(),
            transient_error=True,
        )

    ws_result = _sync_ws_poll(job_id, url, timeout=3.0)
    phase = None
    node = None
    if ws_result:
        phase = ws_result.get("phase")
        node = ws_result.get("node")

    try:
        history = api.get_history(job_id)
    except Exception as e:
        eff_phase = phase or job.get("phase")
        eff_node = node or job.get("node")
        err_obj = _err("POLL_FAILED", f"Failed to poll ComfyUI: {e}")
        store.update_job(
            job_id,
            phase=eff_phase,
            node=eff_node,
            last_polled_at=_now_iso(),
            last_error=json.dumps(err_obj),
        )
        return _snapshot(
            success=False,
            status=job["status"],
            outputs=[],
            error=err_obj,
            metadata=_base_metadata(),
            phase=eff_phase,
            node=eff_node,
            transient_error=True,
        )

    history_entry = history.get(job_id, {})

    if history_entry.get("status", {}).get("errored") or history_entry.get("error"):
        raw_msg = history_entry.get("error") or "Execution error occurred"
        err_obj = _err("COMFYUI_EXECUTION", str(raw_msg))
        store.update_job(
            job_id,
            status="failed",
            error=json.dumps(err_obj),
            phase=phase,
            node=node,
        )
        return _snapshot(
            success=False,
            status="failed",
            outputs=[],
            error=err_obj,
            metadata=_base_metadata(),
            phase=phase,
            node=node,
        )

    outputs = history_entry.get("outputs", {})
    if outputs:
        wf_id = job["workflow_id"]
        config = WORKFLOW_REGISTRY.get(wf_id)
        if config is None:
            err_obj = _err("WORKFLOW_NOT_REGISTERED", f"Workflow '{wf_id}' is not registered.")
            store.update_job(job_id, status="failed", error=json.dumps(err_obj))
            return _snapshot(
                success=False,
                status="failed",
                outputs=[],
                error=err_obj,
                metadata=_base_metadata(),
                phase=phase,
                node=node,
            )

        if results_dir is not None:
            out_dir = results_dir
        else:
            anchor = parse_job_anchor_from_iso(job.get("created_at"))
            out_dir = job_hierarchy_output_dir(
                root,
                job_id,
                anchor=anchor or datetime.now(timezone.utc).astimezone(),
            )
        artifacts, raw_outputs = _materialize_outputs(api, config, root, history_entry, out_dir)

        if not artifacts:
            okind = getattr(config, "output_kind", "image") or "image"
            if okind == "audio":
                kind = "audio"
            elif okind == "video":
                kind = "video"
            else:
                kind = "images"
            err_obj = _err("SAVE_FAILED", f"Could not download output {kind} from ComfyUI.")
            store.update_job(job_id, status="failed", error=json.dumps(err_obj))
            return {**job, "status": "failed", "error": err_obj}

        completed_at = _now_iso()
        outputs_json = json.dumps(artifacts)
        store.update_job(
            job_id,
            status="completed",
            outputs=outputs_json,
            completed_at=completed_at,
            phase=phase,
            node=node,
        )
        metadata = _base_metadata()
        metadata["comfyui_outputs"] = raw_outputs
        return _snapshot(
            success=True,
            status="completed",
            outputs=artifacts,
            error=None,
            metadata=metadata,
            phase=phase,
            node=node,
            completed_at=completed_at,
        )

    # No HTTP outputs yet — merge WS hints without falsely marking completed
    if phase == "finished":
        eff_phase = "waiting_outputs"
        eff_node = None
        new_status = "executing"
    elif phase == "executing":
        eff_phase = "executing"
        eff_node = node
        new_status = "executing"
    else:
        eff_phase = phase or job.get("phase")
        eff_node = node or job.get("node")
        new_status = job["status"]

    update_fields: dict[str, Any] = {"status": new_status}
    if eff_phase is not None:
        update_fields["phase"] = eff_phase
    if eff_node is not None:
        update_fields["node"] = eff_node

    store.update_job(job_id, **update_fields)
    return _snapshot(
        success=False,
        status=new_status,
        outputs=[],
        error=None,
        metadata=_base_metadata(),
        phase=eff_phase or job.get("phase"),
        node=eff_node if eff_node is not None else job.get("node"),
        completed_at=job.get("completed_at"),
    )


def poll_all_jobs(
    store: JobStore,
    poll_server_url: str | None = None,
    *,
    skill_root: Path | None = None,
    results_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Poll all submitted and executing jobs.
    ``poll_server_url``: if ``None``, each job uses its own ``server_url`` from the store.
    """
    pending = store.list_jobs(statuses=("submitted", "executing"), limit=1000)
    results = []
    for job in pending:
        results.append(
            poll_job(
                job["job_id"],
                store,
                poll_server_url,
                skill_root=skill_root,
                results_dir=results_dir,
            )
        )
    return results
