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


# Roles in node_mapping that satisfy a workflow's primary text input. When any
# of these is present the workflow is considered to have a usable prompt path
# and no interactive prompt-node selection is needed at import time.
_PROMPT_LIKE_ROLES = {"prompt", "speech_text", "tags", "lyrics"}


def prompt_is_detected(node_mapping: dict[str, dict]) -> bool:
    """Return True when node_mapping already contains a prompt-like text role."""
    return any(role in _PROMPT_LIKE_ROLES for role in node_mapping)


def collect_prompt_candidates(discovered_nodes: dict[str, dict]) -> list[dict]:
    """Enumerate node fields that could host the user-facing prompt.

    Each candidate is a ``(node, field)`` pair with the field's **current
    value** included, so a maintainer can judge which one is the prompt from
    what the node actually contains (e.g. "a cat on a sofa" is obviously the
    prompt; "euler" is obviously not). A node is a candidate when it has at
    least one scalar string param — this catches text inputs the core
    CLIP/encode heuristic misses (Krea-2 style workflows whose prompt lives in
    a dedicated ``PrimitiveStringMultiline`` node).

    The list is stable-sorted by node title and bounded so an interactive
    picker stays readable on large workflows. Long values are truncated for
    display (the full value stays in ``_discovered_nodes``).
    """
    candidates: list[dict] = []
    for node_key, info in discovered_nodes.items():
        title = node_key.split("#")[0]
        class_type = info.get("class_type", "")
        params = info.get("params") or {}
        for name, value in params.items():
            if infer_scalar_value_type(value) != "string":
                continue
            candidates.append(
                {
                    "title": title,
                    "class_type": class_type,
                    "param": name,
                    "current_value": _truncate_preview(value),
                    "confidence": _prompt_confidence(class_type, name, value, title),
                }
            )
    # Higher-confidence prompt candidates first (so the default re-run hint and
    # the top of the interactive list point at the most likely prompt), then a
    # stable alphabetical tiebreaker.
    candidates.sort(key=lambda c: (-c["confidence"], c["title"].lower(), c["param"]))
    return candidates[:40]


def _prompt_confidence(class_type: str, field: str, value: Any, title: str = "") -> int:
    """Heuristic: how likely is this field the user-facing prompt?

    Higher = more likely. Mirrors the spirit of WebToRun's wizard confidence:
    a CLIPTextEncode.text with a long natural-language value is a strong signal,
    while a short token like "euler" or a file path is a weak one.
    """
    ct = class_type.lower()
    title_hint = title.lower()
    if "clip" in ct and "encode" in ct and field == "text":
        return 30
    # Long multi-word strings (a sentence) look like prompts; short tokens
    # ("euler", "simple") and file paths do not.
    text = str(value or "").strip()
    score = 1
    if " " in text and len(text) >= 12:
        score = 20
    elif len(text) >= 20:
        score = 10
    # A node whose title signals it holds the *user's* prompt beats a system /
    # negative one when several long strings compete.
    if "user" in title_hint or "positive" in title_hint or "main" in title_hint:
        score += 5
    return score


def _truncate_preview(value: Any, limit: int = 60) -> str:
    """Render a scalar value as a short human-readable preview string."""
    if value is None:
        return "(empty)"
    text = str(value).replace("\n", " ").strip()
    if not text:
        return "(empty)"
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


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
    video_input_candidates = []
    audio_input_candidates = []
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
        if class_type == "VHS_LoadVideo" or ("loadvideo" in ct_lower) or ("load video" in title_lower):
            video_input_candidates.append(node_key)
        if class_type == "LoadAudio" or ("loadaudio" in ct_lower) or ("load audio" in title_lower) or ("加载音频" in title):
            audio_input_candidates.append(node_key)
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

    video_role_count = 0
    for node_key in video_input_candidates:
        title = node_key.split("#")[0]
        key = "input_video" if video_role_count == 0 else f"input_video_{video_role_count+1}"
        node_mapping[key] = {
            "node_title": title,
            "param": "video",
            "value_type": "video",
            "input_strategy": "upload",
            "required": True,
        }
        video_role_count += 1

    audio_role_count = 0
    for node_key in audio_input_candidates:
        title = node_key.split("#")[0]
        key = "input_audio" if audio_role_count == 0 else f"input_audio_{audio_role_count+1}"
        node_mapping[key] = {
            "node_title": title,
            "param": "audio",
            "value_type": "audio",
            "input_strategy": "upload",
            "required": True,
        }
        audio_role_count += 1

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
    has_video_input = any(v.get("value_type") == "video" for v in node_mapping.values())
    has_audio_input = any(v.get("value_type") == "audio" for v in node_mapping.values())
    has_media_input = has_image_input or has_video_input or has_audio_input
    if output_kind == "audio":
        capability = "text_to_speech" if tts_candidates else "text_to_music"
    elif output_kind == "video":
        capability = "image_to_video" if has_media_input else "text_to_video"
    else:
        capability = "image_to_image" if has_image_input else "text_to_image"

    input_modes = []
    if any(v.get("value_type") == "string" for v in node_mapping.values()):
        input_modes.append("text")
    if has_image_input:
        input_modes.append("image")
    if has_video_input:
        input_modes.append("video")
    if has_audio_input:
        input_modes.append("audio")
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
        "_prompt_detected": prompt_is_detected(node_mapping),
        "_prompt_candidates": collect_prompt_candidates(nodes),
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
