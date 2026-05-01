"""Run-before-queue checks against ComfyUI HTTP API (nodes + models).

Uses GET /object_info and GET /models[/folder] when available.
Does not execute workflows.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PreflightResult:
    ok: bool
    server_reachable: bool
    missing_node_types: list[str] = field(default_factory=list)
    missing_models: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def http_get_json(server_url: str, path: str, *, timeout: float = 8.0) -> tuple[Any | None, str | None]:
    """GET JSON from ComfyUI. Returns (data, None) or (None, error_message)."""
    base = server_url.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    url = base + path
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if resp.status != 200:
                return None, f"HTTP {resp.status}"
            return json.loads(raw), None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode(errors="replace")
        except OSError:
            body = ""
        return None, f"HTTP {e.code}: {body[:200]}"
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        return None, str(e)


def collect_class_types(workflow: dict[str, Any]) -> set[str]:
    """Unique class_type values from API-format workflow dict."""
    out: set[str] = set()
    for node in workflow.values():
        if isinstance(node, dict):
            ct = node.get("class_type")
            if isinstance(ct, str):
                out.add(ct)
    return out


# (class_type -> inputs key that holds model filename/path string)
_LOADER_MODEL_KEYS: dict[str, tuple[str, ...]] = {
    "UNETLoader": ("unet_name",),
    "VAELoader": ("vae_name",),
    "CLIPLoader": ("clip_name",),
    "CheckpointLoaderSimple": ("ckpt_name",),
    "CLIPVisionLoader": ("clip_name",),
}


def extract_model_references(workflow: dict[str, Any]) -> list[str]:
    """Collect model path strings from loader nodes."""
    refs: list[str] = []
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type")
        if ct not in _LOADER_MODEL_KEYS:
            continue
        inputs = node.get("inputs") or {}
        if not isinstance(inputs, dict):
            continue
        for key in _LOADER_MODEL_KEYS[ct]:
            val = inputs.get(key)
            if isinstance(val, str) and val.strip():
                refs.append(val.strip())
    return refs


def _normalize_ref(ref: str) -> str:
    return ref.replace("\\", "/").strip()


def build_model_availability_index(server_url: str) -> tuple[set[str], list[str]]:
    """Return (flat_set_of_strings, warnings). Flat set includes 'folder/name' and bare filenames."""
    warnings: list[str] = []
    flat: set[str] = set()
    folders_data, err = http_get_json(server_url, "/models")
    if err or not isinstance(folders_data, list):
        warnings.append(f"GET /models failed or unexpected shape: {err!r}")
        return flat, warnings

    for folder in folders_data:
        if not isinstance(folder, str):
            continue
        items, err2 = http_get_json(server_url, f"/models/{folder}")
        if err2:
            warnings.append(f"GET /models/{folder}: {err2}")
            continue
        if not isinstance(items, list):
            warnings.append(f"GET /models/{folder} returned non-list")
            continue
        for name in items:
            if not isinstance(name, str):
                continue
            n = name.replace("\\", "/")
            flat.add(n)
            flat.add(f"{folder}/{n}")
            # also index basename for loose match
            flat.add(n.split("/")[-1])

    return flat, warnings


def _model_ref_is_available(ref: str, flat: set[str]) -> bool:
    n = _normalize_ref(ref)
    if n in flat:
        return True
    base = n.split("/")[-1]
    if base in flat:
        return True
    # suffix match (some APIs return nested paths)
    for candidate in flat:
        if candidate.endswith(n) or candidate.endswith(base):
            return True
    return False


def validate_workflow_resources(server_url: str, workflow: dict[str, Any]) -> PreflightResult:
    """Check node registration via /object_info and model files via /models."""
    obj, err = http_get_json(server_url, "/object_info")
    if err or not isinstance(obj, dict):
        return PreflightResult(
            ok=False,
            server_reachable=False,
            error=err or "object_info not a dict",
        )

    needed = collect_class_types(workflow)
    missing_nodes = sorted(ct for ct in needed if ct not in obj)
    if missing_nodes:
        return PreflightResult(
            ok=False,
            server_reachable=True,
            missing_node_types=missing_nodes,
            error="missing_node_types",
        )

    refs = extract_model_references(workflow)
    if not refs:
        return PreflightResult(ok=True, server_reachable=True)

    flat, warnings = build_model_availability_index(server_url)
    missing_models = [r for r in refs if not _model_ref_is_available(r, flat)]
    ok = len(missing_models) == 0
    return PreflightResult(
        ok=ok,
        server_reachable=True,
        missing_models=sorted(set(_normalize_ref(m) for m in missing_models)),
        warnings=warnings,
        error=None if ok else "missing_models",
    )


def load_workflow_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("workflow root must be a JSON object")
    return data


def preflight_registered_workflow(server_url: str, workflow_path: Path) -> PreflightResult:
    """Load workflow JSON from disk and run :func:`validate_workflow_resources`."""
    wf = load_workflow_json(workflow_path)
    return validate_workflow_resources(server_url, wf)


def build_preflight_cli_payload(workflow_id: str, result: PreflightResult) -> dict[str, Any]:
    """Single JSON object for ``--preflight`` stdout and submitter failure bodies."""
    err: dict[str, str] | None = None
    if not result.ok:
        if not result.server_reachable:
            code = "PREFLIGHT_SERVER_UNREACHABLE"
            msg = result.error or "Cannot reach ComfyUI or GET /object_info failed"
        elif result.missing_node_types:
            code = "PREFLIGHT_MISSING_NODES"
            msg = f"Node types not registered on server: {result.missing_node_types}"
        elif result.missing_models:
            code = "PREFLIGHT_MISSING_MODELS"
            msg = f"Model files not listed under GET /models: {result.missing_models}"
        else:
            code = "PREFLIGHT_FAILED"
            msg = result.error or "Preflight failed"
        err = {"code": code, "message": msg}
    return {
        "success": result.ok,
        "workflow_id": workflow_id,
        "preflight": {
            "server_reachable": result.server_reachable,
            "missing_node_types": result.missing_node_types,
            "missing_models": result.missing_models,
            "warnings": result.warnings,
        },
        "error": err,
    }
