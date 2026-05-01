"""Command-line entry: generation, health check, and save-server."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from comfyui.config import (
    SKILL_ROOT, check_server, get_comfyui_url, job_store_path, local_config_path, save_comfyui_url,
)
from comfyui.services.executor import execute_workflow
from comfyui.services.poller import poll_all_jobs, poll_job
from comfyui.services.submitter import submit_workflow
from comfyui.preflight import build_preflight_cli_payload, preflight_registered_workflow
from comfyui.services.workflow_config import WORKFLOW_REGISTRY, ConfigError
from comfyui.tools.import_workflow import import_workflow, validate_workflow_id

DEFAULT_WORKFLOW = "z_image_turbo"

# If --output ends with a typical media extension, treat it as a file path and use its parent as the save directory.
_IMAGE_LIKE_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".avif"}
)
_AUDIO_LIKE_SUFFIXES = frozenset({".mp3", ".wav", ".flac", ".ogg", ".m4a"})
_VIDEO_LIKE_SUFFIXES = frozenset({".mp4", ".webm", ".mov", ".mkv"})
_MEDIA_OUTPUT_SUFFIXES = _IMAGE_LIKE_SUFFIXES | _AUDIO_LIKE_SUFFIXES | _VIDEO_LIKE_SUFFIXES


def resolve_generate_output(raw: str | None) -> tuple[Path | None, Path | None]:
    """Resolve ``--output`` for ``generate``.

    Returns ``(explicit_dir, relative_under_job)``:

    - Empty → ``(None, None)``: executor writes to per-job
      ``results/%Y%m%d/%H%M%S_{prompt_id}/`` under the skill root (images, audio, video, etc.).
    - Path ending with a known media extension → parent directory as fixed output dir.
    - Absolute path → that directory as fixed output dir.
    - Relative path → ``(None, Path(...))``: appended under each job's hierarchy folder.
    """
    if not raw or not raw.strip():
        return (None, None)
    p = Path(raw.strip()).expanduser()
    if p.suffix.lower() in _MEDIA_OUTPUT_SUFFIXES:
        parent = p.parent
        if parent == Path(".") or str(parent) in (".", ""):
            parent = Path.cwd()
        return (parent.resolve(), None)
    if p.is_absolute():
        return (p.resolve(), None)
    return (None, p)


def resolve_output_directory(raw: str | None, *, fallback: Path) -> Path:
    """Backward-compatible resolver: ``--output`` relative to ``fallback`` (legacy tests).

    Prefer :func:`resolve_generate_output` for CLI generation.
    """
    explicit, rel = resolve_generate_output(raw)
    if explicit is not None:
        return explicit
    if rel is not None:
        return (fallback / rel).resolve()
    return fallback


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


def _cli_run_preflight_only(config, server_url: str) -> int:
    """Print preflight JSON to stdout; return exit code (0 = ok)."""
    path = config.resolve_workflow_path(SKILL_ROOT)
    try:
        pr = preflight_registered_workflow(server_url, path)
    except OSError as e:
        print(
            json.dumps(
                {
                    "success": False,
                    "workflow_id": config.workflow_id,
                    "preflight": {
                        "server_reachable": False,
                        "missing_node_types": [],
                        "missing_models": [],
                        "warnings": [],
                    },
                    "error": {"code": "WORKFLOW_FILE_NOT_FOUND", "message": str(e)},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    except ValueError as e:
        print(
            json.dumps(
                {
                    "success": False,
                    "workflow_id": config.workflow_id,
                    "preflight": {
                        "server_reachable": False,
                        "missing_node_types": [],
                        "missing_models": [],
                        "warnings": [],
                    },
                    "error": {"code": "WORKFLOW_LOAD_FAILED", "message": str(e)},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    payload = build_preflight_cli_payload(config.workflow_id, pr)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if pr.ok else 1


def _cli_preflight_gate_or_exit(server_url: str, config) -> None:
    """Run preflight before generation; exit process with JSON error if not ok."""
    path = config.resolve_workflow_path(SKILL_ROOT)
    try:
        pr = preflight_registered_workflow(server_url, path)
    except OSError as e:
        _print_error_and_exit(
            code="WORKFLOW_FILE_NOT_FOUND",
            message=str(e),
            workflow_id=config.workflow_id,
        )
    except ValueError as e:
        _print_error_and_exit(
            code="WORKFLOW_LOAD_FAILED",
            message=str(e),
            workflow_id=config.workflow_id,
        )
    if pr.ok:
        return
    payload = build_preflight_cli_payload(config.workflow_id, pr)
    err = payload["error"] or {"code": "PREFLIGHT_FAILED", "message": "Preflight failed"}
    _print_error_and_exit(
        code=err["code"],
        message=err["message"],
        workflow_id=config.workflow_id,
        metadata={"preflight": payload["preflight"]},
    )


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
            "Output directory for generated media (images, audio, etc.; filenames from ComfyUI). "
            "Default: per-run results/%%Y%%m%%d/%%H%%M%%S_{job_id}/ under the skill root. "
            "Relative path adds a segment under that job folder; absolute path overrides. "
            "If the path ends with a known media extension, its parent directory is used."
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
        "--width",
        type=int,
        default=None,
        metavar="W",
        help="Output image width (optional; defaults to workflow default).",
    )
    p.add_argument(
        "--height",
        type=int,
        default=None,
        metavar="H",
        help="Output image height (optional; defaults to workflow default).",
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
    p.add_argument(
        "--submit",
        action="store_true",
        help="Submit job(s) to ComfyUI queue without waiting for completion. Returns job_id(s).",
    )
    p.add_argument(
        "--poll",
        metavar="JOB_ID",
        help="Poll a single job's current status.",
    )
    p.add_argument(
        "--poll-all",
        action="store_true",
        help="Poll all pending jobs.",
    )
    p.add_argument(
        "--speech-text",
        default=None,
        metavar="TEXT",
        help="For text-to-speech workflows (e.g. qwen3_tts): spoken content.",
    )
    p.add_argument(
        "--instruct",
        default=None,
        metavar="TEXT",
        help="For qwen3_tts: voice/style instruction text.",
    )
    p.add_argument(
        "--preflight",
        action="store_true",
        help=(
            "Only validate that workflow node types exist in GET /object_info and model paths appear under GET /models; "
            "prints JSON and exits (no prompt or generation required)."
        ),
    )
    p.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip automatic preflight before generate or --submit (advanced / debugging only).",
    )


def _run_single_generate(
    config,
    prompt: str,
    server_url: str,
    results_dir: Path | None,
    output_subdir: Path | None,
    input_images: dict[str, Path] | None,
    progress: bool,
    text_inputs: dict[str, str] | None = None,
    *,
    width: int | None = None,
    height: int | None = None,
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
        output_subdir=output_subdir,
        input_images=input_images or None,
        width=width,
        height=height,
        progress_callback=progress_cb,
        text_inputs=text_inputs,
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

    if getattr(args, "preflight", False):
        return _cli_run_preflight_only(config, server_url)

    prompts = list(args.prompt) + list(args.prompt_flags)
    is_audio_workflow = getattr(config, "output_kind", "image") == "audio"
    is_tts_workflow = getattr(config, "capability", "") == "text_to_speech"

    aw = getattr(args, "width", None)
    ah = getattr(args, "height", None)
    if (aw is None) != (ah is None):
        _print_error_and_exit(
            code="INVALID_PARAM",
            message="--width and --height must be used together, or both omitted.",
            workflow_id=config.workflow_id,
        )
    if is_audio_workflow and (aw is not None or ah is not None):
        _print_error_and_exit(
            code="INVALID_PARAM",
            message="--width and --height apply to image/video workflows only, not audio outputs.",
            workflow_id=config.workflow_id,
        )
    if (
        not is_audio_workflow
        and config.size_strategy == "workflow_managed"
        and (aw is not None or ah is not None)
    ):
        _print_error_and_exit(
            code="INVALID_PARAM",
            message=(
                f"Workflow '{config.workflow_id}' manages output size internally; "
                "--width and --height are not supported. Use a text-to-image workflow (e.g. z_image_turbo) to set dimensions."
            ),
            workflow_id=config.workflow_id,
        )

    has_dim_mapping = (
        config.node_mapping.get("width") is not None
        and config.node_mapping.get("height") is not None
    )
    if (
        not is_audio_workflow
        and config.size_strategy != "workflow_managed"
        and not has_dim_mapping
        and (aw is not None or ah is not None)
    ):
        _print_error_and_exit(
            code="INVALID_PARAM",
            message=(
                f"Workflow '{config.workflow_id}' derives output resolution from the workflow graph "
                "(e.g. uploaded image size); --width and --height are not applicable."
            ),
            workflow_id=config.workflow_id,
        )

    if is_tts_workflow:
        speech = (getattr(args, "speech_text", None) or "").strip()
        instruct = (getattr(args, "instruct", None) or "").strip()
        if prompts:
            _print_error_and_exit(
                code="INVALID_ARGS",
                message="For text-to-speech workflows use --speech-text and --instruct, not positional prompts.",
                workflow_id=config.workflow_id,
            )
        if not speech:
            _print_error_and_exit(
                code="EMPTY_SPEECH_TEXT",
                message="--speech-text is required for this workflow.",
                workflow_id=config.workflow_id,
            )
        if not instruct:
            _print_error_and_exit(
                code="EMPTY_INSTRUCT",
                message="--instruct is required for this workflow.",
                workflow_id=config.workflow_id,
            )
    elif not prompts:
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

    if not getattr(args, "skip_preflight", False):
        _cli_preflight_gate_or_exit(server_url, config)

    explicit_out, output_subdir = resolve_generate_output(args.output)
    count: int = args.count
    results = []
    all_success = True
    progress: bool = getattr(args, "progress", False)

    if is_tts_workflow:
        speech = getattr(args, "speech_text", "") or ""
        instruct = getattr(args, "instruct", "") or ""
        ti = {"speech_text": speech.strip(), "instruct": instruct.strip()}
        for _ in range(count):
            result = _run_single_generate(
                config,
                "",
                server_url,
                explicit_out,
                output_subdir,
                input_images or None,
                progress,
                text_inputs=ti,
                width=aw,
                height=ah,
            )
            results.append(result.to_dict())
            if not result.success:
                all_success = False
        total = count
    else:
        # Generate: count copies per prompt, all go to the same directory
        for prompt in prompts:
            for _ in range(count):
                result = _run_single_generate(
                    config,
                    prompt,
                    server_url,
                    explicit_out,
                    output_subdir,
                    input_images or None,
                    progress,
                    width=aw,
                    height=ah,
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

    # Async mode mutual exclusion
    async_modes = sum(bool(getattr(args, m, False)) for m in ("submit", "poll", "poll_all"))
    if async_modes > 1:
        print(
            json.dumps(
                {
                    "success": False,
                    "workflow_id": args.workflow,
                    "status": "failed",
                    "error": {
                        "code": "MUTUAL_EXCLUSION",
                        "message": "--submit, --poll, and --poll-all are mutually exclusive.",
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    if args.poll and args.submit:
        pass  # handled above

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
    poll_server_url = args.server

    if getattr(args, "preflight", False):
        workflow_id = args.workflow
        if workflow_id not in WORKFLOW_REGISTRY:
            _print_error_and_exit(
                code="WORKFLOW_NOT_REGISTERED",
                message=f"Workflow '{workflow_id}' is not registered",
                workflow_id=workflow_id,
                metadata={"available_workflows": sorted(WORKFLOW_REGISTRY.keys())},
            )
        cfg = WORKFLOW_REGISTRY[workflow_id]
        sys.exit(_cli_run_preflight_only(cfg, server_url))

    if args.check:
        result = check_server(server_url)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["available"] else 1)

    # Async modes: --poll, --poll-all, --submit
    if getattr(args, "poll", None):
        from comfyui.services.job_store import JobStore
        store = JobStore(job_store_path())
        result = poll_job(args.poll, store, poll_server_url)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    if getattr(args, "poll_all", False):
        from comfyui.services.job_store import JobStore
        store = JobStore(job_store_path())
        results = poll_all_jobs(store, poll_server_url)
        print(json.dumps({"jobs": results}, ensure_ascii=False, indent=2))
        sys.exit(0)

    if getattr(args, "submit", False):
        from comfyui.services.job_store import JobStore
        prompts = list(args.prompt) + list(args.prompt_flags)
        store_path = job_store_path()
        input_images: dict[str, Path] = {}
        if args.workflow not in WORKFLOW_REGISTRY:
            _print_error_and_exit(
                code="WORKFLOW_NOT_REGISTERED",
                message=f"Workflow '{args.workflow}' is not registered",
                workflow_id=args.workflow,
                metadata={"available_workflows": sorted(WORKFLOW_REGISTRY.keys())},
            )
        config = WORKFLOW_REGISTRY[args.workflow]
        submit_prompt = ""
        submit_text_inputs: dict[str, str] | None = None

        if config:
            is_tts_submit = getattr(config, "capability", "") == "text_to_speech"
            speech = (getattr(args, "speech_text", None) or "").strip()
            instruct = (getattr(args, "instruct", None) or "").strip()
            if is_tts_submit:
                if prompts:
                    print(
                        json.dumps(
                            {
                                "success": False,
                                "workflow_id": args.workflow,
                                "status": "failed",
                                "error": {
                                    "code": "INVALID_ARGS",
                                    "message": "For TTS workflows use --speech-text and --instruct with --submit.",
                                },
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                    sys.exit(1)
                if not speech or not instruct:
                    print(
                        json.dumps(
                            {
                                "success": False,
                                "workflow_id": args.workflow,
                                "status": "failed",
                                "error": {
                                    "code": "EMPTY_SPEECH_TEXT" if not speech else "EMPTY_INSTRUCT",
                                    "message": "--speech-text and --instruct are required for this workflow.",
                                },
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                    sys.exit(1)
                submit_text_inputs = {"speech_text": speech, "instruct": instruct}
            elif not prompts:
                print(
                    json.dumps(
                        {
                            "success": False,
                            "workflow_id": args.workflow,
                            "status": "failed",
                            "error": {"code": "EMPTY_PROMPT", "message": "Prompt is required for --submit."},
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                sys.exit(1)
            else:
                if len(prompts) > 1:
                    print(
                        json.dumps(
                            {
                                "success": False,
                                "workflow_id": args.workflow,
                                "status": "failed",
                                "error": {
                                    "code": "MULTIPLE_PROMPTS_NOT_SUPPORTED",
                                    "message": "--submit accepts a single prompt only. Submit each prompt individually.",
                                },
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                    sys.exit(1)
                submit_prompt = prompts[0]

        if config:
            image_roles = {k for k, v in config.node_mapping.items() if v.get("value_type") == "image"}
            for img_arg in args.image:
                if "=" in img_arg:
                    key, path_str = img_arg.split("=", 1)
                elif len(image_roles) == 1:
                    key = next(iter(image_roles))
                    path_str = img_arg
                else:
                    key, path_str = None, img_arg
                if key and path_str:
                    img_path = Path(path_str)
                    if not img_path.exists():
                        print(
                            json.dumps(
                                {
                                    "success": False,
                                    "workflow_id": args.workflow,
                                    "status": "failed",
                                    "error": {"code": "INPUT_IMAGE_NOT_FOUND", "message": f"Image file not found: {img_path}"},
                                },
                                ensure_ascii=False,
                                indent=2,
                            )
                        )
                        sys.exit(1)
                    input_images[key] = img_path
        result = submit_workflow(
            workflow_id=args.workflow,
            prompt=submit_prompt,
            skill_root=SKILL_ROOT,
            job_store_path=store_path,
            server_url=server_url,
            input_images=input_images or None,
            width=args.width,
            height=args.height,
            count=args.count,
            text_inputs=submit_text_inputs,
            skip_preflight=getattr(args, "skip_preflight", False),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result.get("submitted") else 1)

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


def cmd_import_workflow() -> int:
    p = argparse.ArgumentParser(description="Import a ComfyUI workflow JSON into assets/workflows and generate a config template.")
    p.add_argument("path", help="Path to an exported ComfyUI workflow JSON (API format).")
    p.add_argument("--id", default=None, help="Optional workflow_id override (default: file stem).")
    p.add_argument("--force", action="store_true", help="Overwrite existing imported files.")
    p.add_argument(
        "--skill-root",
        default=None,
        help="Override skill root directory (advanced; defaults to detected SKILL_ROOT).",
    )
    args = p.parse_args()

    skill_root = Path(args.skill_root or os.environ.get("COMFYUI_SKILL_ROOT") or SKILL_ROOT).resolve()
    raw_id = args.id
    derived_id = (raw_id if raw_id is not None else Path(args.path).stem or "").strip()
    try:
        wid = validate_workflow_id(derived_id)
    except ValueError as e:
        print(
            json.dumps(
                {
                    "success": False,
                    "workflow_id": "unknown",
                    "error": {"code": "INVALID_WORKFLOW_ID", "message": str(e)},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    try:
        payload = import_workflow(
            src_path=Path(args.path),
            skill_root=skill_root,
            workflow_id=wid,
            force=bool(args.force),
        )
    except FileNotFoundError as e:
        err = {"code": "WORKFLOW_FILE_NOT_FOUND", "message": str(e)}
        print(json.dumps({"success": False, "workflow_id": wid, "error": err}, ensure_ascii=False, indent=2))
        return 1
    except FileExistsError:
        err = {"code": "WORKFLOW_ALREADY_EXISTS", "message": f"Workflow '{wid}' already exists. Use --force to overwrite."}
        print(json.dumps({"success": False, "workflow_id": wid, "error": err}, ensure_ascii=False, indent=2))
        return 1
    except ValueError as e:
        err = {"code": "WORKFLOW_JSON_INVALID", "message": str(e)}
        print(json.dumps({"success": False, "workflow_id": wid, "error": err}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
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
                            "Supported flags: --prompt/-p, --output, --workflow/-w, --count, --width, --height, --server, --image, --progress. "
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

    # Handle --poll and --poll-all directly (skip run_generate_from_args which checks server)
    if getattr(args, "poll", None):
        from comfyui.services.job_store import JobStore

        store = JobStore(job_store_path())
        result = poll_job(args.poll, store, args.server)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if getattr(args, "poll_all", False):
        from comfyui.services.job_store import JobStore

        store = JobStore(job_store_path())
        results = poll_all_jobs(store, args.server)
        print(json.dumps({"jobs": results}, ensure_ascii=False, indent=2))
        return 0

    # --submit is handled in main_run_script()
    if getattr(args, "submit", False):
        # Require explicit --workflow (no implicit default for --submit)
        if "--workflow" not in sys.argv and "-w" not in sys.argv:
            print(
                json.dumps(
                    {
                        "success": False,
                        "workflow_id": args.workflow,
                        "status": "failed",
                        "error": {
                            "code": "WORKFLOW_REQUIRED",
                            "message": "--submit requires an explicit --workflow flag",
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1
        main_run_script()
        return 1  # fallback if main_run_script() returns without exiting

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
    if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help"):
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

    # No args: fall through to generate (will report missing prompt via EMPTY_PROMPT)
    if len(sys.argv) < 2:
        sys.exit(cmd_generate())

    sub = sys.argv[1]

    # Route subcommands FIRST (before any flag checks)
    if sub in ("check", "save-server", "generate", "import-workflow"):
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        if sub == "check":
            sys.exit(cmd_check())
        if sub == "save-server":
            sys.exit(cmd_save_server())
        if sub == "import-workflow":
            sys.exit(cmd_import_workflow())
        sys.exit(cmd_generate())

    # Handle --check flag (not a subcommand)
    if "--check" in sys.argv[1:]:
        # Strip --check and delegate to cmd_check
        sys.argv = [sys.argv[0]] + [a for a in sys.argv[2:] if a != "--check"]
        sys.exit(cmd_check())

    # Handle --save-server flag (not a subcommand)
    if "--save-server" in sys.argv[1:]:
        idx = sys.argv.index("--save-server")
        url_arg = sys.argv[idx + 1] if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--") else None
        # Build new argv: [prog, url, ...remaining args except --save-server and its value]
        remaining = [a for i, a in enumerate(sys.argv) if i not in (idx, idx + 1)]
        sys.argv = [sys.argv[0], url_arg] + remaining[1:]
        sys.exit(cmd_save_server())

    # Handle --server flag (without a subcommand) by delegating to main_run_script()
    if "--server" in sys.argv[1:]:
        main_run_script()
        return

    # If any async flag is in argv, delegate entirely to generate parser
    # This prevents flags like --server from being misinterpreted as subcommands
    async_flags = {"--submit", "--poll", "--poll-all"}
    if async_flags & set(sys.argv[1:]):
        # Check mutual exclusion among async flags
        present = [f for f in async_flags if f in sys.argv[1:]]
        if len(present) > 1:
            print(
                json.dumps(
                    {
                        "success": False,
                        "workflow_id": "z_image_turbo",
                        "status": "failed",
                        "error": {
                            "code": "MUTUAL_EXCLUSION",
                            "message": "--submit, --poll, and --poll-all are mutually exclusive.",
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            sys.exit(1)
        sys.exit(cmd_generate())

    print(
        f"未知子命令: {sub}。使用: check | save-server | generate",
        file=sys.stderr,
    )
    sys.exit(2)
