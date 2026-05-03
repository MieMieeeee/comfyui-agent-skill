#!/usr/bin/env python3
"""CLI entry point for workflow analyzer.

Usage:
    python analyze_workflow.py <workflow.json> [--force]

By default writes to <workflow>.config.template.json to avoid overwriting
human-reviewed configs. Use --force to write directly to <workflow>.config.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from comfyui.tools.analyze_workflow import analyze_workflow, detect_custom_plugins


def main() -> None:
    args = sys.argv[1:]
    force = "--force" in args
    if force:
        args.remove("--force")

    if not args:
        print("Usage: python analyze_workflow.py <workflow.json> [--force]")
        sys.exit(1)

    workflow_path = Path(args[0])
    if not workflow_path.exists():
        print(f"Error: {workflow_path} not found")
        sys.exit(1)

    config = analyze_workflow(workflow_path)

    # Try to detect third-party plugins via /object_info
    try:
        from comfyui.preflight import http_get_json
        from comfyui.config import get_comfyui_url
        server_url = get_comfyui_url()
        obj, obj_err = http_get_json(server_url, "/object_info")
        if not obj_err and isinstance(obj, dict):
            plugins = detect_custom_plugins(obj, config["_discovered_nodes"])
            if plugins:
                config["_required_plugins"] = plugins
    except Exception:
        pass  # server unavailable — skip plugin detection

    config_path = workflow_path.parent / f"{workflow_path.stem}.config.json"
    template_path = workflow_path.parent / f"{workflow_path.stem}.config.template.json"

    if force:
        out_path = config_path
    else:
        out_path = template_path
        if config_path.exists():
            print(f"Warning: {config_path} exists (reviewed config).")

    out_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated: {out_path}")
    print(f"Discovered {len(config['_discovered_nodes'])} nodes, {len(config['node_mapping'])} mapped params")
    if config.get("_required_plugins"):
        print(f"Required third-party plugins: {config['_required_plugins']}")
    if config.get("_required_models"):
        print(f"Required models: {len(config['_required_models'])} files")
    if not force:
        print(f"Review the template, then rename to {config_path.name} when ready.")
    else:
        print("Review and edit the config file before using it.")


if __name__ == "__main__":
    main()
