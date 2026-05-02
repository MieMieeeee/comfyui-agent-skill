from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from comfyui.config import SKILL_ROOT, check_server, get_comfyui_url, job_store_path
from comfyui.preflight import build_preflight_cli_payload, preflight_registered_workflow
from comfyui.services.executor import execute_workflow
from comfyui.services.poller import poll_all_jobs, poll_job
from comfyui.services.submitter import submit_workflow
from comfyui.services.workflow_config import WORKFLOW_REGISTRY, ConfigError


DEFAULT_WORKFLOW = "z_image_turbo"

_IMAGE_LIKE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".avif"})
_AUDIO_LIKE_SUFFIXES = frozenset({".mp3", ".wav", ".flac", ".ogg", ".m4a"})
_VIDEO_LIKE_SUFFIXES = frozenset({".mp4", ".webm", ".mov", ".mkv"})
_MEDIA_OUTPUT_SUFFIXES = _IMAGE_LIKE_SUFFIXES | _AUDIO_LIKE_SUFFIXES | _VIDEO_LIKE_SUFFIXES


def resolve_generate_output(raw: str | None) -> tuple[Path | None, Path | None]:
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
            ensure_ascii=True,
            indent=2,
        )
    )
    sys.exit(1)


def _cli_run_preflight_only(config, server_url: str) -> int:
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
                ensure_ascii=True,
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
                ensure_ascii=True,
                indent=2,
            )
        )
        return 1
    payload = build_preflight_cli_payload(config.workflow_id, pr)
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if pr.ok else 1


def _cli_preflight_gate_or_exit(server_url: str, config) -> None:
    path = config.resolve_workflow_path(SKILL_ROOT)
    try:
        pr = preflight_registered_workflow(server_url, path)
    except OSError as e:
        _print_error_and_exit(code="WORKFLOW_FILE_NOT_FOUND", message=str(e), workflow_id=config.workflow_id)
    except ValueError as e:
        _print_error_and_exit(code="WORKFLOW_LOAD_FAILED", message=str(e), workflow_id=config.workflow_id)
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
        help="One or more text prompts. Use -p for each additional prompt. All prompts share --output, --workflow, --server, --count, --image.",
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
    p.add_argument("--count", type=int, default=1, help="Repeat count per prompt (default: 1).")
    p.add_argument("--width", type=int, default=None, metavar="W", help="Output image width (optional).")
    p.add_argument("--height", type=int, default=None, metavar="H", help="Output image height (optional).")
    p.add_argument("--image", action="append", default=[], metavar="KEY=PATH", help="Input image: 'key=path' or bare path; repeat for multiple keys")
    p.add_argument("--progress", action="store_true", help="Print JSON progress lines to stderr during generation")
    p.add_argument("--submit", action="store_true", help="Submit job(s) to ComfyUI queue without waiting for completion. Returns job_id(s).")
    p.add_argument("--poll", metavar="JOB_ID", help="Poll a single job's current status.")
    p.add_argument("--poll-all", action="store_true", help="Poll all pending jobs.")
    p.add_argument("--speech-text", default=None, metavar="TEXT", help="For text-to-speech workflows (e.g. qwen3_tts): spoken content.")
    p.add_argument("--instruct", default=None, metavar="TEXT", help="For qwen3_tts: voice/style instruction text.")
    p.add_argument(
        "--preflight",
        action="store_true",
        help="Only validate workflow node types and model references; prints JSON and exits (no prompt required).",
    )
    p.add_argument("--skip-preflight", action="store_true", help="Skip automatic preflight before generate or --submit (debug only).")


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
            print(json.dumps({"event": "comfyui_progress", **ev}, ensure_ascii=True), file=sys.stderr)

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
        _print_error_and_exit(code="INVALID_PARAM", message="--width and --height must be used together, or both omitted.", workflow_id=config.workflow_id)
    if is_audio_workflow and (aw is not None or ah is not None):
        _print_error_and_exit(code="INVALID_PARAM", message="--width and --height apply to image/video workflows only, not audio outputs.", workflow_id=config.workflow_id)
    if (not is_audio_workflow and config.size_strategy == "workflow_managed" and (aw is not None or ah is not None)):
        _print_error_and_exit(
            code="INVALID_PARAM",
            message=f"Workflow '{config.workflow_id}' manages output size internally; --width/--height are not supported.",
            workflow_id=config.workflow_id,
        )

    has_dim_mapping = config.node_mapping.get("width") is not None and config.node_mapping.get("height") is not None
    if (not is_audio_workflow and config.size_strategy != "workflow_managed" and not has_dim_mapping and (aw is not None or ah is not None)):
        _print_error_and_exit(
            code="INVALID_PARAM",
            message=f"Workflow '{config.workflow_id}' derives output resolution from the workflow graph; --width/--height are not applicable.",
            workflow_id=config.workflow_id,
        )

    if is_tts_workflow:
        speech = (getattr(args, "speech_text", None) or "").strip()
        instruct = (getattr(args, "instruct", None) or "").strip()
        if prompts:
            _print_error_and_exit(code="INVALID_ARGS", message="For text-to-speech workflows use --speech-text and --instruct, not positional prompts.", workflow_id=config.workflow_id)
        if not speech:
            _print_error_and_exit(code="EMPTY_SPEECH_TEXT", message="--speech-text is required for this workflow.", workflow_id=config.workflow_id)
        if not instruct:
            _print_error_and_exit(code="EMPTY_INSTRUCT", message="--instruct is required for this workflow.", workflow_id=config.workflow_id)
    elif not prompts:
        _print_error_and_exit(code="EMPTY_PROMPT", message='A prompt is required. Example: python -m comfyui generate -p "..."', workflow_id=config.workflow_id)

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
            _print_error_and_exit(code="INPUT_IMAGE_NOT_FOUND", message=f"Image file not found: {img_path}", workflow_id=config.workflow_id)
        input_images[key] = img_path

    health = check_server(server_url)
    if not health["available"]:
        err_line = f"ComfyUI server not available at {server_url}: {health.get('error')}"
        if health.get("hint"):
            err_line = f"{err_line}\n{health['hint']}"
        _print_error_and_exit(code="SERVER_UNAVAILABLE", message=err_line, workflow_id=config.workflow_id, status="server_unavailable")

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
            result = _run_single_generate(config, "", server_url, explicit_out, output_subdir, input_images or None, progress, text_inputs=ti, width=aw, height=ah)
            results.append(result.to_dict())
            if not result.success:
                all_success = False
        total = count
    else:
        for prompt in prompts:
            for _ in range(count):
                result = _run_single_generate(config, prompt, server_url, explicit_out, output_subdir, input_images or None, progress, width=aw, height=ah)
                results.append(result.to_dict())
                if not result.success:
                    all_success = False
        total = len(prompts) * count

    if total == 1:
        print(json.dumps(results[0], ensure_ascii=True, indent=2))
    else:
        print(json.dumps({"count": total, "success": all_success, "results": results}, ensure_ascii=True, indent=2))
    return 0 if all_success else 1


class _SilentArgumentParser(argparse.ArgumentParser):
    def print_help(self, file=None) -> None:  # type: ignore[override]
        return super().print_help(file=sys.stderr)

    def print_usage(self, file=None) -> None:  # type: ignore[override]
        return super().print_usage(file=sys.stderr)

    def error(self, message: str) -> None:
        raise SystemExit(2)


def cmd_generate() -> int:
    p = _SilentArgumentParser(description=f"Run a registered ComfyUI workflow (default: {DEFAULT_WORKFLOW})")
    _add_generate_arguments(p, default_workflow=DEFAULT_WORKFLOW)
    try:
        args = p.parse_args()
    except SystemExit as e:
        if getattr(e, "code", 1) == 0:
            return 0
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
                            "Supported flags: --prompt/-p, --output, --workflow/-w, --count, --width, --height, --server, --image, "
                            "--progress, --preflight, --skip-preflight, --submit, --poll, --poll-all, --speech-text, --instruct. "
                            "Use 'python -m comfyui generate -p \"your prompt\"' to start."
                        ),
                    },
                    "metadata": {},
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 1

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
                ensure_ascii=True,
                indent=2,
            )
        )
        return 1

    if getattr(args, "poll", None):
        from comfyui.services.job_store import JobStore

        store = JobStore(job_store_path())
        result = poll_job(args.poll, store, args.server)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0

    if getattr(args, "poll_all", False):
        from comfyui.services.job_store import JobStore

        store = JobStore(job_store_path())
        results = poll_all_jobs(store, args.server)
        print(json.dumps({"jobs": results}, ensure_ascii=True, indent=2))
        return 0

    if getattr(args, "submit", False):
        if "--workflow" not in sys.argv and "-w" not in sys.argv:
            print(json.dumps({"success": False, "workflow_id": args.workflow, "status": "failed", "error": {"code": "WORKFLOW_REQUIRED", "message": "--submit requires an explicit --workflow flag"}}, ensure_ascii=True, indent=2))
            return 1
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

        is_tts_submit = getattr(config, "capability", "") == "text_to_speech"
        speech = (getattr(args, "speech_text", None) or "").strip()
        instruct = (getattr(args, "instruct", None) or "").strip()
        if is_tts_submit:
            if prompts:
                print(json.dumps({"success": False, "workflow_id": args.workflow, "status": "failed", "error": {"code": "INVALID_ARGS", "message": "For TTS workflows use --speech-text and --instruct with --submit."}}, ensure_ascii=True, indent=2))
                return 1
            if not speech or not instruct:
                print(json.dumps({"success": False, "workflow_id": args.workflow, "status": "failed", "error": {"code": "EMPTY_SPEECH_TEXT" if not speech else "EMPTY_INSTRUCT", "message": "--speech-text and --instruct are required for this workflow."}}, ensure_ascii=True, indent=2))
                return 1
            submit_text_inputs = {"speech_text": speech, "instruct": instruct}
        elif not prompts:
            print(json.dumps({"success": False, "workflow_id": args.workflow, "status": "failed", "error": {"code": "EMPTY_PROMPT", "message": "Prompt is required for --submit."}}, ensure_ascii=True, indent=2))
            return 1
        else:
            if len(prompts) > 1:
                print(json.dumps({"success": False, "workflow_id": args.workflow, "status": "failed", "error": {"code": "MULTIPLE_PROMPTS_NOT_SUPPORTED", "message": "--submit accepts a single prompt only. Submit each prompt individually."}}, ensure_ascii=True, indent=2))
                return 1
            submit_prompt = prompts[0]

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
                    print(json.dumps({"success": False, "workflow_id": args.workflow, "status": "failed", "error": {"code": "INPUT_IMAGE_NOT_FOUND", "message": f"Image file not found: {img_path}"}}, ensure_ascii=True, indent=2))
                    return 1
                input_images[key] = img_path

        comfyui_url = get_comfyui_url()
        server_url = args.server or comfyui_url
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
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result.get("submitted") else 1

    try:
        return run_generate_from_args(args)
    except ConfigError as e:
        print(json.dumps({"success": False, "workflow_id": "unknown", "status": "failed", "outputs": [], "job_id": None, "error": {"code": "CONFIG_ERROR", "message": str(e)}, "metadata": {}}, ensure_ascii=True, indent=2))
        return 1
