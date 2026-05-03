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
    missing_plugins: list[str] = field(default_factory=list)
    required_plugins: list[str] = field(default_factory=list)
    missing_models: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class ModelRef:
    """A model file reference extracted from a workflow loader node."""
    path: str
    model_type: str   # e.g. "diffusion_model", "vae", "clip"
    loader: str       # class_type of the loader node
    folder: str       # expected ComfyUI models subdirectory


# Loader class_type -> (model_type, default_folder)
_LOADER_MODEL_CATEGORIES: dict[str, tuple[str, str]] = {
    "UNETLoader": ("diffusion_model", "diffusion_models"),
    "UnetLoaderGGUF": ("diffusion_model", "diffusion_models"),
    "VAELoader": ("vae", "vae"),
    "VAELoaderKJ": ("vae", "vae"),
    "CLIPLoader": ("clip", "clip"),
    "CheckpointLoaderSimple": ("checkpoint", "checkpoints"),
    "CLIPVisionLoader": ("clip_vision", "clip_vision"),
    "DualCLIPLoader": ("clip", "clip"),
    "LoraLoaderModelOnly": ("lora", "loras"),
    "LatentUpscaleModelLoader": ("upscale_model", "upscale_models"),
    "LTXVAudioVAELoader": ("audio_vae", "vae"),
    "LTXAVTextEncoderLoader": ("text_encoder", "clip"),
}


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
    "UnetLoaderGGUF": ("unet_name",),
    "VAELoader": ("vae_name",),
    "VAELoaderKJ": ("vae_name",),
    "CLIPLoader": ("clip_name",),
    "CheckpointLoaderSimple": ("ckpt_name",),
    "CLIPVisionLoader": ("clip_name",),
    "DualCLIPLoader": ("clip_name1", "clip_name2"),
    "LoraLoaderModelOnly": ("lora_name",),
    "LatentUpscaleModelLoader": ("model_name",),
    "LTXVAudioVAELoader": ("ckpt_name",),
    "LTXAVTextEncoderLoader": ("text_encoder", "ckpt_name"),
}


def extract_model_references(workflow: dict[str, Any]) -> list[ModelRef]:
    """Collect model references from loader nodes.

    Each reference includes the file path, model type (e.g. "diffusion_model"),
    loader node class_type, and expected ComfyUI models subdirectory.
    """
    refs: list[ModelRef] = []
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type")
        if ct not in _LOADER_MODEL_KEYS:
            continue
        inputs = node.get("inputs") or {}
        if not isinstance(inputs, dict):
            continue
        cat_type, cat_folder = _LOADER_MODEL_CATEGORIES.get(ct, ("unknown", "models"))
        for key in _LOADER_MODEL_KEYS[ct]:
            val = inputs.get(key)
            if isinstance(val, str) and val.strip():
                refs.append(ModelRef(
                    path=val.strip(),
                    model_type=cat_type,
                    loader=ct,
                    folder=cat_folder,
                ))
    return refs


def detect_custom_plugins(
    object_info: dict[str, Any],
    needed_class_types: set[str],
) -> tuple[list[str], list[str]]:
    """Detect third-party custom node plugins required by a workflow.

    Uses the ``python_module`` field from ``/object_info`` to distinguish
    built-in nodes (``nodes``, ``comfy_extras.*``) from third-party
    plugins (``custom_nodes.*``).

    Returns ``(required_plugins, missing_plugins)`` where each entry is
    a plugin package name (e.g. ``"ComfyUI-GGUF"``).
    """
    required: set[str] = set()
    missing: list[str] = []

    for ct in needed_class_types:
        info = object_info.get(ct)
        if not info:
            continue
        module = info.get("python_module", "")
        if not module.startswith("custom_nodes."):
            continue
        parts = module.split(".")
        plugin_name = parts[1] if len(parts) >= 2 else module
        required.add(plugin_name)

    return sorted(required), sorted(missing)


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


def _model_ref_is_available(ref: ModelRef, flat: set[str]) -> bool:
    n = _normalize_ref(ref.path)
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
    """Check node registration, plugin dependencies, and model files."""
    obj, err = http_get_json(server_url, "/object_info")
    if err or not isinstance(obj, dict):
        return PreflightResult(
            ok=False,
            server_reachable=False,
            error=err or "object_info not a dict",
        )

    needed = collect_class_types(workflow)
    missing_nodes = sorted(ct for ct in needed if ct not in obj)

    required_plugins, _ = detect_custom_plugins(obj, needed)

    warnings: list[str] = []
    missing_models: list[dict[str, str]] = []
    refs = extract_model_references(workflow)
    if refs:
        flat, model_warnings = build_model_availability_index(server_url)
        warnings.extend(model_warnings)
        seen: set[str] = set()
        for ref in refs:
            norm = _normalize_ref(ref.path)
            if norm in seen:
                continue
            if not _model_ref_is_available(ref, flat):
                seen.add(norm)
                missing_models.append({
                    "path": norm,
                    "type": ref.model_type,
                    "folder": ref.folder,
                })
        missing_models.sort(key=lambda m: m["path"])

    has_errors = bool(missing_nodes or missing_models)
    error = None
    if missing_nodes:
        error = "missing_node_types"
    elif missing_models:
        error = "missing_models"

    return PreflightResult(
        ok=not has_errors,
        server_reachable=True,
        missing_node_types=missing_nodes,
        required_plugins=required_plugins,
        missing_models=missing_models,
        warnings=warnings,
        error=error,
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
        elif result.missing_plugins:
            code = "PREFLIGHT_MISSING_PLUGINS"
            msg = f"Third-party plugins not installed: {result.missing_plugins}"
        elif result.missing_models:
            code = "PREFLIGHT_MISSING_MODELS"
            details = [f"{m['path']} (type={m['type']}, folder={m['folder']})" for m in result.missing_models]
            msg = f"Model files not found: {details}"
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
            "required_plugins": result.required_plugins,
            "missing_plugins": result.missing_plugins,
            "missing_models": result.missing_models,
            "warnings": result.warnings,
        },
        "error": err,
    }
