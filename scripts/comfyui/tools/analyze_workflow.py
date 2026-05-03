"""Analyze a ComfyUI workflow JSON and generate a config JSON template."""
from __future__ import annotations

import json
from pathlib import Path


def analyze_workflow(workflow_path: Path) -> dict:
    """Read a ComfyUI workflow JSON and produce a config template."""
    data = json.loads(workflow_path.read_text(encoding="utf-8"))
    workflow_name = workflow_path.stem

    nodes = {}
    title_counts: dict[str, int] = {}
    output_candidates = []
    sampler_candidates = []
    latent_candidates = []
    prompt_candidates = []
    loader_candidates = []

    # Loader node types and their model-path input keys
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

    for node_id, node in data.items():
        meta = node.get("_meta", {})
        title = meta.get("title", node.get("class_type", f"Node_{node_id}"))
        class_type = node.get("class_type", "")
        inputs = node.get("inputs", {})

        scalar_params = {}
        for key, val in inputs.items():
            if not isinstance(val, list):
                scalar_params[key] = val

        # Use title as key; append #N suffix only for duplicates
        title_counts[title] = title_counts.get(title, 0) + 1
        node_key = title if title_counts[title] == 1 else f"{title}#{title_counts[title]}"

        nodes[node_key] = {
            "id": node_id,
            "class_type": class_type,
            "params": scalar_params,
        }

        ct_lower = class_type.lower()
        title_lower = title.lower()

        if "save" in ct_lower or "save" in title_lower:
            output_candidates.append(node_key)
        if "sampler" in ct_lower or "ksampler" in ct_lower:
            sampler_candidates.append(node_key)
        if "latent" in ct_lower or "empty" in ct_lower:
            latent_candidates.append(node_key)
        if "clip" in ct_lower and "encode" in ct_lower:
            prompt_candidates.append(node_key)
        if class_type in _LOADER_MODEL_KEYS:
            loader_candidates.append(node_key)

    # Build node_mapping
    node_mapping: dict[str, dict] = {}

    for node_key in prompt_candidates:
        node_info = nodes[node_key]
        title = node_key.split("#")[0]
        params = node_info["params"]
        text_param = "text" if "text" in params else next(iter(params), "text")

        if "negative" in title.lower():
            key = "negative_prompt"
        elif "positive" in title.lower():
            key = "prompt"
        else:
            key = f"text_input_{len(node_mapping)}"

        entry = {"node_title": title, "param": text_param, "value_type": "string"}
        if key == "prompt":
            entry["required"] = True
        node_mapping[key] = entry

    for node_key in sampler_candidates:
        node_info = nodes[node_key]
        title = node_key.split("#")[0]
        if "seed" in node_info["params"]:
            node_mapping["seed"] = {
                "node_title": title,
                "param": "seed",
                "value_type": "integer",
                "auto_random": True,
            }

    for node_key in latent_candidates:
        node_info = nodes[node_key]
        title = node_key.split("#")[0]
        params = node_info["params"]
        if "width" in params:
            node_mapping["width"] = {
                "node_title": title,
                "param": "width",
                "value_type": "integer",
                "default": params["width"],
            }
        if "height" in params:
            node_mapping["height"] = {
                "node_title": title,
                "param": "height",
                "value_type": "integer",
                "default": params["height"],
            }

    # Extract model file references from loader nodes
    required_models: list[str] = []
    for node_key in loader_candidates:
        node_info = nodes[node_key]
        class_type = node_info["class_type"]
        params = node_info["params"]
        for key in _LOADER_MODEL_KEYS[class_type]:
            val = params.get(key)
            if isinstance(val, str) and val.strip():
                required_models.append(val.strip())

    output_node_title = output_candidates[0].split("#")[0] if output_candidates else "REVIEW_NEEDED"

    return {
        "workflow_id": workflow_name,
        "workflow_file": workflow_path.name,
        "output_node_title": output_node_title,
        "capability": "REVIEW: text_to_image | image_to_image | etc.",
        "description": "REVIEW: Add description",
        "node_mapping": node_mapping,
        "_discovered_nodes": nodes,
        "_required_models": required_models,
    }


def detect_custom_plugins(
    object_info: dict,
    discovered_nodes: dict[str, dict],
) -> list[str]:
    """Detect third-party custom node plugins from ComfyUI /object_info.

    Uses the ``python_module`` field to distinguish built-in nodes
    (``nodes``, ``comfy_extras.*``) from third-party plugins
    (``custom_nodes.*``).

    Args:
        object_info: Parsed JSON from ``GET /object_info``.
        discovered_nodes: The ``_discovered_nodes`` dict from :func:`analyze_workflow`.

    Returns:
        Sorted list of plugin package names (e.g. ``["ComfyUI-GGUF", "comfyui-videohelpersuite"]``).
    """
    required: set[str] = set()
    for _nid, info in discovered_nodes.items():
        ct = info.get("class_type", "")
        server_info = object_info.get(ct)
        if not server_info:
            continue
        module = server_info.get("python_module", "")
        if not module.startswith("custom_nodes."):
            continue
        parts = module.split(".")
        plugin_name = parts[1] if len(parts) >= 2 else module
        required.add(plugin_name)
    return sorted(required)
