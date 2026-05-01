"""Analyze a ComfyUI workflow JSON and generate a config JSON template."""
from __future__ import annotations

import json
from pathlib import Path


def analyze_workflow(workflow_path: Path) -> dict:
    """Read a ComfyUI workflow JSON and produce a config template."""
    data = json.loads(workflow_path.read_text(encoding="utf-8"))
    workflow_name = workflow_path.stem

    nodes = {}
    output_candidates = []
    sampler_candidates = []
    latent_candidates = []
    prompt_candidates = []

    for node_id, node in data.items():
        meta = node.get("_meta", {})
        title = meta.get("title", node.get("class_type", f"Node_{node_id}"))
        class_type = node.get("class_type", "")
        inputs = node.get("inputs", {})

        scalar_params = {}
        for key, val in inputs.items():
            if not isinstance(val, list):
                scalar_params[key] = val

        nodes[title] = {
            "id": node_id,
            "class_type": class_type,
            "params": scalar_params,
        }

        ct_lower = class_type.lower()
        title_lower = title.lower()

        if "save" in ct_lower or "save" in title_lower:
            output_candidates.append(title)
        if "sampler" in ct_lower or "ksampler" in ct_lower:
            sampler_candidates.append(title)
        if "latent" in ct_lower or "empty" in ct_lower:
            latent_candidates.append(title)
        if "clip" in ct_lower and "encode" in ct_lower:
            prompt_candidates.append(title)

    # Build node_mapping
    node_mapping: dict[str, dict] = {}

    for title in prompt_candidates:
        node_info = nodes[title]
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

    for title in sampler_candidates:
        node_info = nodes[title]
        if "seed" in node_info["params"]:
            node_mapping["seed"] = {
                "node_title": title,
                "param": "seed",
                "value_type": "integer",
                "auto_random": True,
            }

    for title in latent_candidates:
        node_info = nodes[title]
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

    output_node_title = output_candidates[0] if output_candidates else "REVIEW_NEEDED"

    return {
        "workflow_id": workflow_name,
        "workflow_file": workflow_path.name,
        "output_node_title": output_node_title,
        "capability": "REVIEW: text_to_image | image_to_image | etc.",
        "description": "REVIEW: Add description",
        "node_mapping": node_mapping,
        "_discovered_nodes": nodes,
    }
