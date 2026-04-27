"""Command-line entry: generation, health check, and save-server."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from comfyui.config import SKILL_ROOT, check_server, get_comfyui_url, local_config_path, save_comfyui_url
from comfyui.services.executor import execute_workflow
from comfyui.services.workflow_config import WORKFLOW_REGISTRY, ConfigError

DEFAULT_WORKFLOW = "z_image_turbo"

# If --output ends with a typical image extension, treat it as a file path and use its parent as the save directory.
_IMAGE_LIKE_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".avif"}
)


def resolve_output_directory(raw: str | None, *, fallback: Path) -> Path:
    """Resolve CLI ``--output`` to a results directory.

    - ``None`` or empty → ``fallback`` (typically ``results/<workflow_id>/``).
    - Path ending with a known image extension → parent directory (e.g. ``E:/tmp/out.png`` → ``E:/tmp``).
    - Otherwise → treated as a subdirectory name under ``fallback``;
      i.e. ``--output foo/bar`` → ``fallback/foo/bar``.
      The directory is created if it does not exist.
    """
    if not raw or not raw.strip():
        return fallback
    p = Path(raw.strip()).expanduser()
    if p.suffix.lower() in _IMAGE_LIKE_SUFFIXES:
        parent = p.parent
        if parent == Path(".") or str(parent) in (".", ""):
            parent = Path.cwd()
        return parent.resolve()
    return (fallback / p).resolve()


def _print_error_and_exit(
    *,
    code: str,
    message: str,
    workflow_id: str,
    status: str = "failed",
    metadata: dict | None = None,
) -> None:
    print(
        json.dumps(
            {
                "success": False,
                "workflow_id": workflow_id,
                "status": status,
                "outputs": [],
                "job_id": None,
                "error": {"code": code, "message": message},
                "metadata": metadata or {},
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    sys.exit(1)


def _add_generate_arguments(p: argparse.ArgumentParser, *, default_workflow: str) -> None:
    p.add_argument(
        "prompt",
        nargs="*",
        metavar="PROMPT",
        help="One or more text prompts. Use -p for each additional prompt. "
             "All prompts share --output, --workflow, --server, --count, --image.",
    )
    p.add_argument(
        "--prompt",
        "-p",
        action="append",
        dest="prompt_flags",
        default=[],
        metavar="TEXT",
        help="Additional prompt (can be specified multiple times).",
    )
    p.add_argument("--server", default=None, help="ComfyUI server URL (default: from config or 127.0.0.1:8188)")
    p.add_argument(
        "--output",
        default=None,
        metavar="DIR",
        help=(
            "Output directory for all generated images (filenames are chosen by ComfyUI). "
            "If the path ends with an image extension, its parent directory is used."
        ),
    )
    p.add_argument(
        "--workflow",
        "-w",
        default=default_workflow,
        help=f"Workflow to use (default: {default_workflow}; available: {', '.join(sorted(WORKFLOW_REGISTRY.keys()))})",
    )
    p.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of images to generate per prompt (default: 1). Total images = len(prompts) × count.",
    )
    p.add_argument(
        "--image",
        action="append",
        default=[],
        metavar="KEY=PATH",
        help="Input image: 'key=path' or bare path; repeat for multiple keys",
    )
    p.add_argument(
        "--progress",
        action="store_true",
        help="Print JSON progress lines to stderr during generation",
    )


def _run_single_generate(
    config,
    prompt: str,
    server_url: str,
    results_dir: Path,
    input_images: dict[str, Path] | None,
    progress: bool,
) -> Any:
    progress_cb: Callable[[dict[str, Any]], None] | None = None
    if progress:

        def _cb(ev: dict[str, Any]) -> None:
            print(
                json.dumps({"event": "comfyui_progress", **ev}, ensure_ascii=False),
                file=sys.stderr,
            )

        progress_cb = _cb
    return execute_workflow(
        config=config,
        prompt=prompt,
        skill_root=SKILL_ROOT,
        server_url=server_url,
        results_dir=results_dir,
        input_images=input_images or None,
        progress_callback=progress_cb,
    )


def run_generate_from_args(args: argparse.Namespace) -> int:
    """Run generation; returns process exit code (0 = success)."""
    comfyui_url = get_comfyui_url()
    server_url = args.server or comfyui_url
    workflow_id = args.workflow
    if workflow_id not in WORKFLOW_REGISTRY:
        _print_error_and_exit(
            code="WORKFLOW_NOT_REGISTERED",
            message=f"Workflow '{workflow_id}' is not registered",
            workflow_id=workflow_id,
            metadata={"available_workflows": sorted(WORKFLOW_REGISTRY.keys())},
        )
    config = WORKFLOW_REGISTRY[workflow_id]
    prompts = list(args.prompt) + list(args.prompt_flags)
    if not prompts:
        _print_error_and_exit(
            code="EMPTY_PROMPT",
            message='A prompt is required. Example: python -m comfyui generate -p "..."',
            workflow_id=config.workflow_id,
        )

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

    health = check_server(server_url)
    if not health["available"]:
        err_line = f"ComfyUI server not available at {server_url}: {health['error']}"
        if health.get("hint"):
            err_line = f"{err_line}\n{health['hint']}"
        _print_error_and_exit(
            code="SERVER_UNAVAILABLE",
            message=err_line,
            workflow_id=config.workflow_id,
            status="server_unavailable",
        )

    default_results = SKILL_ROOT / "results" / config.workflow_id
    results_dir = resolve_output_directory(args.output, fallback=default_results)
    count: int = args.count
    results = []
    all_success = True
    progress: bool = getattr(args, "progress", False)

    # Generate: count copies per prompt, all go to the same directory
    for prompt in prompts:
        for _ in range(count):
            result = _run_single_generate(
                config, prompt, server_url, results_dir, input_images or None, progress
            )
            results.append(result.to_dict())
            if not result.success:
                all_success = False

    total = len(prompts) * count
    if total == 1:
        print(json.dumps(results[0], ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {"count": total, "success": all_success, "results": results},
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0 if all_success else 1


def main_run_script() -> None:
    """Entry for `__main__.py` and backwards compatibility."""
    comfyui_url = get_comfyui_url()
    parser = argparse.ArgumentParser(
        description="ComfyUI text-to-image / image edit (use `python -m comfyui` for subcommands).",
    )
    parser.add_argument("--check", action="store_true", help="Check if ComfyUI server is available and exit")
    parser.add_argument(
        "--save-server",
        metavar="URL",
        help="Save a ComfyUI server URL to config.local.json for future use",
    )
    _add_generate_arguments(parser, default_workflow=DEFAULT_WORKFLOW)
    args = parser.parse_args()

    if args.save_server:
        save_comfyui_url(args.save_server)
        print(
            json.dumps(
                {
                    "saved": True,
                    "comfyui_url": args.save_server,
                    "config_file": str(local_config_path()),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(0)

    server_url = args.server or comfyui_url
    if args.check:
        result = check_server(server_url)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["available"] else 1)

    try:
        code = run_generate_from_args(args)
    except ConfigError as e:
        print(
            json.dumps(
                {
                    "success": False,
                    "workflow_id": "unknown",
                    "status": "failed",
                    "outputs": [],
                    "job_id": None,
                    "error": {"code": "CONFIG_ERROR", "message": str(e)},
                    "metadata": {},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)
    sys.exit(code)


def cmd_check() -> int:
    p = argparse.ArgumentParser(description="Check ComfyUI /system_stats")
    p.add_argument("--server", default=None, help="ComfyUI server URL")
    args = p.parse_args()
    url = args.server or get_comfyui_url()
    result = check_server(url)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["available"] else 1


def cmd_save_server() -> int:
    p = argparse.ArgumentParser(description="Save ComfyUI base URL to config.local.json")
    p.add_argument("url", help="e.g. http://192.168.1.10:8188")
    args = p.parse_args()
    save_comfyui_url(args.url)
    print(
        json.dumps(
            {
                "saved": True,
                "comfyui_url": args.url,
                "config_file": str(local_config_path()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


class _SilentArgumentParser(argparse.ArgumentParser):
    """Parser that reports errors as return values instead of exiting."""

    def error(self, message: str) -> None:
        raise SystemExit(2)


def cmd_generate() -> int:
    p = _SilentArgumentParser(
        description="Run a registered ComfyUI workflow (default: z_image_turbo)",
    )
    _add_generate_arguments(p, default_workflow=DEFAULT_WORKFLOW)
    try:
        args = p.parse_args()
    except SystemExit:
        print(
            json.dumps(
                {
                    "success": False,
                    "workflow_id": DEFAULT_WORKFLOW,
                    "status": "failed",
                    "outputs": [],
                    "job_id": None,
                    "error": {
                        "code": "INVALID_PARAM",
                        "message": (
                            "Unrecognized or unsupported arguments. "
                            "Supported flags: --prompt/-p, --output, --workflow/-w, --count, --server, --image, --progress. "
                            "Use 'python -m comfyui generate -p \"your prompt\"' to start."
                        ),
                    },
                    "metadata": {},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    try:
        return run_generate_from_args(args)
    except ConfigError as e:
        print(
            json.dumps(
                {
                    "success": False,
                    "workflow_id": "unknown",
                    "status": "failed",
                    "outputs": [],
                    "job_id": None,
                    "error": {"code": "CONFIG_ERROR", "message": str(e)},
                    "metadata": {},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1


def main_module() -> None:
    """`python -m comfyui` 子命令: check | save-server | generate"""
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(
            "用法:\n"
            "  python -m comfyui check               # 健康检查\n"
            "  python -m comfyui save-server URL    # 保存服务器地址\n"
            "  python -m comfyui generate [选项]    # 出图\n"
            "\n"
            "示例:\n"
            "  python -m comfyui generate -p \"a cat\" --output ./out\n"
            "  python -m comfyui generate -p \"happy cat\" -p \"sad cat\" -p \"surprised cat\" --output ./expressions\n"
            "  python -m comfyui generate --workflow klein_edit --image input_image=photo.png -p \"change outfit\"",
            file=sys.stderr,
        )
        sys.exit(0)
    sub = sys.argv[1]
    if sub not in ("check", "save-server", "generate"):
        print(
            f"未知子命令: {sub}。使用: check | save-server | generate",
            file=sys.stderr,
        )
        sys.exit(2)
    # Repoint argv for subcommand parsers
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    if sub == "check":
        sys.exit(cmd_check())
    if sub == "save-server":
        sys.exit(cmd_save_server())
    sys.exit(cmd_generate())
