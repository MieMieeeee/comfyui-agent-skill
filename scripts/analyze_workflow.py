#!/usr/bin/env python3
"""CLI entry point for workflow analyzer.

Usage:
    python analyze_workflow.py <workflow.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from comfyui.tools.analyze_workflow import analyze_workflow  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python analyze_workflow.py <workflow.json>")
        sys.exit(1)

    workflow_path = Path(sys.argv[1])
    if not workflow_path.exists():
        print(f"Error: {workflow_path} not found")
        sys.exit(1)

    config = analyze_workflow(workflow_path)

    config_path = workflow_path.parent / f"{workflow_path.stem}.config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated: {config_path}")
    print(f"Discovered {len(config['_discovered_nodes'])} nodes, {len(config['node_mapping'])} mapped params")
    print("Review and edit the config file before using it.")


if __name__ == "__main__":
    main()
