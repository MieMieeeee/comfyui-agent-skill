#!/usr/bin/env python3
"""CLI entry point for ComfyUI text-to-image generation.

Usage:
    python run.py "a cute cat sitting on a windowsill"
    python run.py --prompt "a sunset over mountains" --server http://192.168.1.100:8188
    python run.py --workflow z_image_turbo --prompt "a landscape"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure the scripts/ directory is on sys.path so `comfyui` package is importable.
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from comfyui.config import COMFYUI_URL, SKILL_ROOT, check_server  # noqa: E402
from comfyui.services.executor import execute_workflow  # noqa: E402
from comfyui.services.workflow_config import WORKFLOW_REGISTRY  # noqa: E402

DEFAULT_WORKFLOW = "z_image_turbo"


def main() -> None:
    parser = argparse.ArgumentParser(description="ComfyUI text-to-image generation")
    parser.add_argument("prompt", nargs="?", help="Text prompt for image generation")
    parser.add_argument("--prompt", "-p", dest="prompt_flag", help="Text prompt (alternative positional)")
    parser.add_argument("--server", default=None, help=f"ComfyUI server URL (default: {COMFYUI_URL})")
    parser.add_argument("--output", default=None, help="Output directory for generated images")
    parser.add_argument("--check", action="store_true", help="Check if ComfyUI server is available and exit")
    parser.add_argument(
        "--workflow", "-w",
        default=DEFAULT_WORKFLOW,
        choices=list(WORKFLOW_REGISTRY.keys()),
        help=f"Workflow to use (default: {DEFAULT_WORKFLOW})",
    )
    args = parser.parse_args()

    server_url = args.server or COMFYUI_URL

    # Health check mode
    if args.check:
        result = check_server(server_url)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["available"] else 1)

    # Resolve workflow config
    config = WORKFLOW_REGISTRY[args.workflow]

    # Determine prompt
    prompt = args.prompt or args.prompt_flag
    if not prompt:
        parser.error("A prompt is required. Usage: python run.py \"your prompt text\"")

    # Check server availability
    health = check_server(server_url)
    if not health["available"]:
        print(json.dumps({
            "success": False,
            "workflow_id": config.workflow_id,
            "status": "server_unavailable",
            "error": {
                "code": "SERVER_UNAVAILABLE",
                "message": f"ComfyUI server not available at {server_url}: {health['error']}",
            },
        }, ensure_ascii=False))
        sys.exit(1)

    # Resolve output dir
    results_dir = Path(args.output) if args.output else SKILL_ROOT / "results" / config.workflow_id

    # Execute
    result = execute_workflow(
        config=config,
        prompt=prompt,
        skill_root=SKILL_ROOT,
        server_url=server_url,
        results_dir=results_dir,
    )

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
