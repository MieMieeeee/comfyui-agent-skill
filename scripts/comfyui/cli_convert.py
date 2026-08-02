"""Command-line entry: convert ComfyUI UI/Save workflows to API format.

Drives a running ComfyUI front-end via Playwright (reusing its authoritative
``loadGraphData`` + ``graphToPrompt``) to translate litegraph ``{nodes, links}``
files into ``/prompt``-ready API JSON. Does not trigger model inference.

See ``docs/convert_ui_workflows.md`` for the full rationale.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from comfyui.config import get_comfyui_url
from comfyui.tools.convert_ui_workflow import (
    FORMAT_API,
    FORMAT_UI,
    convert_ui_to_api,
    convert_ui_workflows_dir,
    load_and_classify,
)


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_convert_ui() -> int:
    p = argparse.ArgumentParser(
        prog="convert-ui",
        description=(
            "Convert ComfyUI UI/Save format workflows ({nodes, links}) to API format "
            "by driving a running ComfyUI front-end. Requires Playwright + Chromium. "
            "Does not trigger inference. Output files drop straight into ComfyUI."
        ),
    )
    p.add_argument("source", help="A single UI/Save workflow JSON, or a directory of them.")
    p.add_argument(
        "-o",
        "--output",
        default=None,
        help=(
            "Output path. For a single file: the destination JSON (default: <source>.api.json). "
            "For a directory: the destination directory, mirroring the subtree "
            "(default: <source>/api_workflows)."
        ),
    )
    p.add_argument("--server", default=None, help="ComfyUI server URL (default: configured/saved URL).")
    p.add_argument("--timeout", type=int, default=120_000, help="Per-file Playwright wait timeout in ms.")
    args = p.parse_args()

    url = args.server or get_comfyui_url()
    src = Path(args.source)

    if not src.exists():
        _emit({"success": False, "error": {"code": "SOURCE_NOT_FOUND", "message": f"source not found: {src}"}})
        return 1

    # Directory mode -> batch.
    if src.is_dir():
        out = Path(args.output) if args.output else src / "api_workflows"
        try:
            report = convert_ui_workflows_dir(src, out, comfy_url=url, timeout_ms=args.timeout)
        except RuntimeError as e:
            # Lazily-imported playwright missing / browser launch failure.
            _emit({"success": False, "error": {"code": "CONVERT_RUNTIME_ERROR", "message": str(e)}})
            return 1
        _emit(report.to_dict())
        return 0 if not report.failures else 1

    # Single-file mode.
    out = Path(args.output) if args.output else src.with_suffix(".api.json")
    try:
        fmt, data = load_and_classify(src)
    except ValueError as e:
        _emit({"success": False, "source": str(src), "error": {"code": "WORKFLOW_JSON_INVALID", "message": str(e)}})
        return 1

    if fmt == FORMAT_API:
        _emit(
            {
                "success": True,
                "source": str(src),
                "status": "skipped_api",
                "message": "already API format; nothing to do.",
            }
        )
        return 0

    if fmt != FORMAT_UI:
        _emit(
            {
                "success": False,
                "source": str(src),
                "error": {
                    "code": "WORKFLOW_NOT_UI_FORMAT",
                    "message": "source is neither UI/Save ({nodes, links}) nor API format.",
                },
            }
        )
        return 1

    try:
        api_json, ui_nodes = convert_ui_to_api(data, comfy_url=url, timeout_ms=args.timeout)
    except RuntimeError as e:
        _emit({"success": False, "source": str(src), "error": {"code": "CONVERT_RUNTIME_ERROR", "message": str(e)}})
        return 1
    except Exception as e:  # playwright/transit errors, front-end eval failure, etc.
        _emit(
            {
                "success": False,
                "source": str(src),
                "error": {"code": "CONVERT_FAILED", "message": f"{type(e).__name__}: {e}"},
            }
        )
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    # No {"prompt": ...} wrapper: it would make ComfyUI treat the file as UI/Save
    # and render an "Empty canvas" on drag-in (see docs/convert_ui_workflows.md §2).
    out.write_text(json.dumps(api_json, ensure_ascii=False, indent=2), encoding="utf-8")
    _emit(
        {
            "success": True,
            "source": str(src),
            "output": str(out),
            "status": "converted",
            "ui_nodes": ui_nodes,
            "api_nodes": len(api_json),
        }
    )
    return 0
