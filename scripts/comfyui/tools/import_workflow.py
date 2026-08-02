from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Any

from comfyui.config import SKILL_ROOT, get_user_data_root, get_workflows_dir
from comfyui.services.workflow_config import Z_IMAGE_TURBO, load_configs_from_dir
from comfyui.tools.analyze_workflow import analyze_workflow
from comfyui.tools.convert_ui_workflow import (
    FORMAT_API,
    FORMAT_UI,
    WorkflowFormatError,
    classify_workflow_format,
)


_WORKFLOW_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def validate_workflow_id(raw: str) -> str:
    wid = (raw or "").strip().lower()
    if not wid or not _WORKFLOW_ID_RE.fullmatch(wid):
        raise ValueError("workflow_id must match ^[a-z0-9][a-z0-9_-]{0,63}$")
    return wid


def import_workflow(
    *,
    src_path: Path,
    workflow_id: str | None,
    force: bool,
    into_project: bool,
    user_data_root: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    if not src_path.exists():
        raise FileNotFoundError(f"workflow json not found: {src_path}")

    # Validate JSON *and* format. analyze_workflow assumes API format
    # ({"1": {"class_type":..., "inputs":...}}); feeding it a UI/Save file
    # ({"nodes":[...], "links":[...]}) crashes with AttributeError. Detect that
    # here with an actionable message instead.
    try:
        data = json.loads(src_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid workflow json: {e}") from e

    fmt = classify_workflow_format(data)
    if fmt == FORMAT_UI:
        raise WorkflowFormatError(
            "this is a ComfyUI UI/Save format workflow ({nodes, links}), not the API format "
            "this skill runs. Re-export it from ComfyUI: enable Settings -> Enable Dev mode options, "
            "then use the 'Save (API)' button (not 'Save'). "
            "To batch-convert existing UI workflows, run: python -m comfyui convert-ui --help"
        )
    if fmt != FORMAT_API:
        raise WorkflowFormatError(
            "workflow JSON is neither UI/Save format ({nodes, links}) nor API format "
            "({\"1\": {\"class_type\":..., \"inputs\":...}}). Re-export from ComfyUI using "
            "the 'Save (API)' button (requires Settings -> Enable Dev mode options)."
        )

    wid = validate_workflow_id(workflow_id or src_path.stem)

    builtin_ids = set(load_configs_from_dir(get_workflows_dir()).keys())
    builtin_ids.add(Z_IMAGE_TURBO.workflow_id)
    if wid in builtin_ids:
        if into_project:
            if not force:
                raise ValueError(
                    f"workflow_id conflicts with an existing built-in workflow_id: {wid} (use --force to overwrite)"
                )
        else:
            raise ValueError(f"workflow_id conflicts with built-in workflow_id: {wid}")

    if into_project:
        root = (project_root or SKILL_ROOT).resolve()
        workflows_dir = root / "assets" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        dst_json = workflows_dir / f"{wid}.json"
        dst_tpl = workflows_dir / f"{wid}.config.template.json"
        if not force and (dst_json.exists() or dst_tpl.exists()):
            raise FileExistsError(f"workflow already exists: {wid}")
        dst_json.write_bytes(src_path.read_bytes())
        config = analyze_workflow(dst_json)
        config["workflow_id"] = wid
        config["workflow_file"] = f"{wid}.json"
        dst_tpl.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        data_root = (user_data_root or get_user_data_root()).resolve()
        custom_root = (data_root / "custom_workflows").resolve()
        wf_dir = custom_root / wid
        wf_dir.mkdir(parents=True, exist_ok=True)
        dst_json = wf_dir / "workflow.json"
        dst_src = wf_dir / "workflow.source.json"
        dst_tpl = wf_dir / "workflow.config.template.json"
        if not force and (dst_json.exists() or dst_tpl.exists() or (wf_dir / "workflow.config.json").exists()):
            raise FileExistsError(f"workflow already exists: {wid}")
        payload_bytes = src_path.read_bytes()
        dst_src.write_bytes(payload_bytes)
        dst_json.write_bytes(payload_bytes)
        config = analyze_workflow(dst_json)
        config["schema_version"] = 1
        config["workflow_id"] = wid
        config["workflow_file"] = f"{wid}/workflow.json"
        config["source"] = {
            "kind": "user_imported",
            "imported_at": _dt.datetime.now(tz=_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "origin_file": str(src_path.resolve()),
        }
        dst_tpl.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "success": True,
        "workflow_id": wid,
        "workflow_path": str(dst_json),
        "template_path": str(dst_tpl),
        "next_steps": [
            f"Review {Path(dst_tpl).name} and confirm the minimal required fields (description/capability/output_kind + exposed inputs in node_mapping).",
            "Optionally add selection metadata (intent_categories/priority/keywords_any/selection_guidance) to help Agents choose the workflow.",
            (
                f"Rename the reviewed template to workflow.config.json to activate it."
                if not into_project
                else f"Rename the reviewed template to {wid}.config.json to register it."
            ),
            f"Optional preflight: uv run --no-sync python -m comfyui generate --workflow {wid} --preflight",
        ],
    }
