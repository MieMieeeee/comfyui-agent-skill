#!/usr/bin/env python3
"""CLI entry point for ComfyUI image generation and editing.

Usage:
    python run.py "a cute cat sitting on a windowsill"
    python run.py --count 2 --prompt "a sunset over mountains"
    python run.py --workflow z_image_turbo --prompt "a landscape"
    python run.py --workflow klein_edit --image input_image=photo.png --prompt "change hair to pink"
    python run.py --save-server http://192.168.1.100:8188
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure the scripts/ directory is on sys.path so `comfyui` package is importable.
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from comfyui.config import SKILL_ROOT, check_server, get_comfyui_url, save_comfyui_url  # noqa: E402
from comfyui.services.executor import execute_workflow  # noqa: E402
from comfyui.services.workflow_config import WORKFLOW_REGISTRY, ConfigError  # noqa: E402

DEFAULT_WORKFLOW = "z_image_turbo"


def _print_error_and_exit(
    *,
    code: str,
    message: str,
    workflow_id: str,
    status: str = "failed",
    metadata: dict | None = None,
) -> None:
    print(json.dumps({
        "success": False,
        "workflow_id": workflow_id,
        "status": status,
        "outputs": [],
        "job_id": None,
        "error": {"code": code, "message": message},
        "metadata": metadata or {},
    }, ensure_ascii=False, indent=2))
    sys.exit(1)


def main() -> None:
    comfyui_url = get_comfyui_url()

    parser = argparse.ArgumentParser(description="ComfyUI text-to-image generation")
    parser.add_argument("prompt", nargs="?", help="Text prompt for image generation")
    parser.add_argument("--prompt", "-p", dest="prompt_flag", help="Text prompt (alternative positional)")
    parser.add_argument("--server", default=None, help=f"ComfyUI server URL (default: {comfyui_url})")
    parser.add_argument("--output", default=None, help="Output directory for generated images")
    parser.add_argument("--check", action="store_true", help="Check if ComfyUI server is available and exit")
    parser.add_argument(
        "--save-server", metavar="URL",
        help="Save a ComfyUI server URL to config.local.json for future use",
    )
    parser.add_argument(
        "--workflow", "-w",
        default=DEFAULT_WORKFLOW,
        help=f"Workflow to use (default: {DEFAULT_WORKFLOW}; available: {', '.join(sorted(WORKFLOW_REGISTRY.keys()))})",
    )
    parser.add_argument("--count", type=int, default=1, help="Number of images to generate (default: 1)")
    parser.add_argument(
        "--image", action="append", default=[], metavar="KEY=PATH",
        help="Input image: 'key=path' (e.g. --image input_image=photo.png) or bare path for single-image workflows",
    )
    args = parser.parse_args()

    # Save server URL mode
    if args.save_server:
        save_comfyui_url(args.save_server)
        print(json.dumps({
            "saved": True,
            "comfyui_url": args.save_server,
            "config_file": str(SKILL_ROOT / "config.local.json"),
        }, ensure_ascii=False, indent=2))
        sys.exit(0)

    server_url = args.server or comfyui_url

    # Health check mode
    if args.check:
        result = check_server(server_url)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["available"] else 1)

    # Resolve workflow config
    workflow_id = args.workflow
    if workflow_id not in WORKFLOW_REGISTRY:
        _print_error_and_exit(
            code="WORKFLOW_NOT_REGISTERED",
            message=f"Workflow '{workflow_id}' is not registered",
            workflow_id=workflow_id,
            metadata={"available_workflows": sorted(WORKFLOW_REGISTRY.keys())},
        )
    config = WORKFLOW_REGISTRY[workflow_id]

    # Determine prompt
    prompt = args.prompt or args.prompt_flag
    if not prompt:
        _print_error_and_exit(
            code="EMPTY_PROMPT",
            message="A prompt is required. Usage: python run.py \"your prompt text\"",
            workflow_id=config.workflow_id,
        )

    # Parse --image arguments (before server check — pure local validation)
    input_images: dict[str, Path] = {}
    image_roles = {k for k, v in config.node_mapping.items() if v.get("value_type") == "image"}
    for img_arg in args.image:
        if "=" in img_arg:
            key, path_str = img_arg.split("=", 1)
        elif len(image_roles) == 1:
            key = next(iter(image_roles))
            path_str = img_arg
        else:
            _print_error_and_exit(
                code="INVALID_PARAM_TYPE",
                message=f"Image argument must be 'key=path' when workflow has multiple image inputs. Available roles: {sorted(image_roles)}",
                workflow_id=config.workflow_id,
            )
        img_path = Path(path_str)
        if not img_path.exists():
            _print_error_and_exit(
                code="INPUT_IMAGE_NOT_FOUND",
                message=f"Image file not found: {img_path}",
                workflow_id=config.workflow_id,
            )
        input_images[key] = img_path

    # Check server availability
    health = check_server(server_url)
    if not health["available"]:
        _print_error_and_exit(
            code="SERVER_UNAVAILABLE",
            message=f"ComfyUI server not available at {server_url}: {health['error']}",
            workflow_id=config.workflow_id,
            status="server_unavailable",
        )

    # Resolve output dir
    results_dir = Path(args.output) if args.output else SKILL_ROOT / "results" / config.workflow_id

    # Execute — loop for count > 1, incrementing seed
    count = args.count
    results = []
    all_success = True

    for i in range(count):
        result = execute_workflow(
            config=config,
            prompt=prompt,
            skill_root=SKILL_ROOT,
            server_url=server_url,
            results_dir=results_dir,
            input_images=input_images or None,
        )
        results.append(result.to_dict())
        if not result.success:
            all_success = False

    # Output: single result for count=1, list for count>1
    if count == 1:
        print(json.dumps(results[0], ensure_ascii=False, indent=2))
    else:
        output = {
            "count": count,
            "success": all_success,
            "results": results,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))

    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    try:
        main()
    except ConfigError as e:
        print(json.dumps({
            "success": False,
            "workflow_id": "unknown",
            "status": "failed",
            "outputs": [],
            "job_id": None,
            "error": {"code": "CONFIG_ERROR", "message": str(e)},
            "metadata": {},
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
