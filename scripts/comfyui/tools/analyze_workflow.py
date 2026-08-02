"""Analyze a ComfyUI workflow JSON and generate a config JSON template."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_SKILL_TITLE_RE = re.compile(r"^skill(?:[\s:\]\-_]|$)", re.IGNORECASE)

_KNOWN_HINT_ROLES: dict[str, str] = {
    "input_image": "image",
    "prompt": "text",
    "negative_prompt": "text",
    "seed": "seed",
    "width": "width",
    "height": "height",
    "speech_text": "text",
    "instruct": "instruct",
}


def parse_skill_hint(title: str) -> str | None:
    """Return the hint after a leading ``Skill`` prefix, or ``None`` if not a Skill node."""
    if not _SKILL_TITLE_RE.match(title):
        return None
    remainder = re.sub(r"^skill[\s:\]\-_]*", "", title, count=1, flags=re.IGNORECASE).strip()
    return remainder


def slugify_hint(hint: str) -> str:
    slug = re.sub(r"[^\w]+", "_", hint.lower(), flags=re.UNICODE)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "skill_node"


def infer_scalar_value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    return "string"


def mapped_node_params(node_mapping: dict[str, dict]) -> set[tuple[str, str]]:
    return {(entry["node_title"], entry["param"]) for entry in node_mapping.values()}


def skill_role_name(hint: str, param: str, node_mapping: dict[str, dict]) -> str:
    """Derive a stable mapping role for a Skill-prefixed node parameter."""
    slug = slugify_hint(hint)
    normalized_hint = hint.lower().replace(" ", "_").strip("_")

    for role, expected_param in _KNOWN_HINT_ROLES.items():
        if normalized_hint == role and param == expected_param and role not in node_mapping:
            return role
        if hint.lower().strip() == role.replace("_", " ") and param == expected_param and role not in node_mapping:
            return role

    if param == "image" and "input_image" not in node_mapping:
        return "input_image"
    if param == "text" and "prompt" not in node_mapping:
        return "prompt"

    if param not in node_mapping:
        return param

    candidate = f"{slug}_{param}"
    if candidate not in node_mapping:
        return candidate

    index = 2
    while f"{candidate}_{index}" in node_mapping:
        index += 1
    return f"{candidate}_{index}"


def apply_skill_node_mappings(nodes: dict[str, dict], node_mapping: dict[str, dict]) -> None:
    """Expose scalar inputs on Skill-prefixed nodes without overriding existing heuristics."""
    already_mapped = mapped_node_params(node_mapping)

    for node_key, node_info in nodes.items():
        title = node_key.split("#")[0]
        hint = parse_skill_hint(title)
        if hint is None:
            continue

        params = node_info.get("params") or {}
        for param, value in params.items():
            if (title, param) in already_mapped:
                continue

            value_type = infer_scalar_value_type(value)
            role = skill_role_name(hint, param, node_mapping)
            entry: dict[str, Any] = {
                "node_title": title,
                "param": param,
                "value_type": value_type,
                "source": "skill_prefix",
            }

            if value_type == "image":
                entry["input_strategy"] = "upload"
                entry["required"] = True
            elif value_type == "string" and role == "prompt":
                entry["required"] = True
            else:
                entry["default"] = value

            node_mapping[role] = entry
            already_mapped.add((title, param))


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
    image_input_candidates = []
    tts_candidates = []
    ace_audio_candidates = []

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

        if ("save" in ct_lower) or ("save" in title_lower) or ("videocombine" in ct_lower) or ("video combine" in title_lower):
            output_candidates.append(node_key)
        if "sampler" in ct_lower or "ksampler" in ct_lower:
            sampler_candidates.append(node_key)
        if "latent" in ct_lower or "empty" in ct_lower:
            latent_candidates.append(node_key)
        if "clip" in ct_lower and "encode" in ct_lower:
            prompt_candidates.append(node_key)
        if class_type in _LOADER_MODEL_KEYS:
            loader_candidates.append(node_key)
        if class_type == "LoadImage" or ("loadimage" in ct_lower) or ("load image" in title_lower):
            image_input_candidates.append(node_key)
        if ("tts" in ct_lower) or ("tts" in title_lower) or ("voicedesign" in ct_lower) or ("voicedesign" in title_lower):
            if "text" in scalar_params and "instruct" in scalar_params:
                tts_candidates.append(node_key)
        if ("acestep" in ct_lower) or ("ace step" in title_lower) or ("audio1.5" in ct_lower):
            if "tags" in scalar_params:
                ace_audio_candidates.append(node_key)

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

    image_role_count = 0
    for node_key in image_input_candidates:
        node_info = nodes[node_key]
        title = node_key.split("#")[0]
        key = "input_image" if image_role_count == 0 else f"input_image_{image_role_count+1}"
        node_mapping[key] = {
            "node_title": title,
            "param": "image",
            "value_type": "image",
            "input_strategy": "upload",
            "required": True,
        }
        image_role_count += 1

    if tts_candidates:
        node_key = tts_candidates[0]
        title = node_key.split("#")[0]
        node_mapping["speech_text"] = {
            "node_title": title,
            "param": "text",
            "value_type": "string",
            "required": True,
        }
        node_mapping["instruct"] = {
            "node_title": title,
            "param": "instruct",
            "value_type": "string",
            "required": True,
        }

    if ace_audio_candidates:
        node_key = ace_audio_candidates[0]
        title = node_key.split("#")[0]
        node_mapping["prompt"] = {
            "node_title": title,
            "param": "tags",
            "value_type": "string",
            "required": True,
        }
        node_mapping["lyrics"] = {
            "node_title": title,
            "param": "lyrics",
            "value_type": "string",
        }

    apply_skill_node_mappings(nodes, node_mapping)

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

    def _pick_output_node_title() -> str:
        if not output_candidates:
            return "REVIEW_NEEDED"
        best = output_candidates[0]
        best_score = -1
        for cand in output_candidates:
            title = cand.split("#")[0]
            info = nodes.get(cand, {})
            params = info.get("params", {})
            ct = (info.get("class_type") or "").lower()
            t = title.lower()
            score = 0
            if "primary" in t:
                score += 10
            if params.get("save_output") is True:
                score += 8
            if "save" in ct or "save" in t:
                score += 5
            if score > best_score:
                best_score = score
                best = cand
        return best.split("#")[0]

    output_node_title = _pick_output_node_title()

    output_kind = "image"
    output_title_lower = output_node_title.lower()
    output_info = next((nodes[k] for k in output_candidates if k.split("#")[0] == output_node_title), None)
    output_ct_lower = (output_info.get("class_type", "").lower() if output_info else "")
    if ("audio" in output_title_lower) or ("mp3" in output_title_lower) or ("audio" in output_ct_lower):
        output_kind = "audio"
    elif ("video" in output_title_lower) or ("mp4" in output_title_lower) or ("video" in output_ct_lower):
        output_kind = "video"

    has_image_input = any(v.get("value_type") == "image" for v in node_mapping.values())
    if output_kind == "audio":
        capability = "text_to_speech" if tts_candidates else "text_to_music"
    elif output_kind == "video":
        capability = "image_to_video" if has_image_input else "text_to_video"
    else:
        capability = "image_to_image" if has_image_input else "text_to_image"

    input_modes = []
    if any(v.get("value_type") == "string" for v in node_mapping.values()):
        input_modes.append("text")
    if has_image_input:
        input_modes.append("image")
    if not input_modes:
        input_modes = ["text"]

    return {
        "workflow_id": workflow_name,
        "workflow_file": workflow_path.name,
        "output_node_title": output_node_title,
        "capability": capability,
        "description": "TODO: Describe what this workflow does.",
        "output_kind": output_kind,
        "intent_categories": [],
        "input_modes": input_modes,
        "priority": 0,
        "keywords_any": [],
        "selection_guidance": {"agent_hint": ""},
        "node_mapping": node_mapping,
        "_required_fields": [
            "description",
            "capability",
            "output_kind",
            "node_mapping",
        ],
        "_optional_fields": [
            "intent_categories",
            "input_modes",
            "priority",
            "keywords_any",
            "selection_guidance",
            "resolution_presets",
            "default_resolution",
        ],
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
