from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from comfyui.tools.analyze_workflow import analyze_workflow


_WORKFLOW_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def validate_workflow_id(raw: str) -> str:
    wid = (raw or "").strip().lower()
    if not wid or not _WORKFLOW_ID_RE.fullmatch(wid):
        raise ValueError("workflow_id must match ^[a-z0-9][a-z0-9_-]{0,63}$")
    return wid


def import_workflow(
    *,
    src_path: Path,
    skill_root: Path,
    workflow_id: str | None,
    force: bool,
) -> dict[str, Any]:
    if not src_path.exists():
        raise FileNotFoundError(f"workflow json not found: {src_path}")

    try:
        json.loads(src_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid workflow json: {e}") from e

    wid = validate_workflow_id(workflow_id or src_path.stem)
    workflows_dir = skill_root / "assets" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    dst_json = workflows_dir / f"{wid}.json"
    dst_tpl = workflows_dir / f"{wid}.config.template.json"

    if not force and (dst_json.exists() or dst_tpl.exists()):
        raise FileExistsError(f"workflow already exists: {wid}")

    dst_json.write_bytes(src_path.read_bytes())
    config = analyze_workflow(dst_json)
    dst_tpl.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "success": True,
        "workflow_id": wid,
        "workflow_path": str(dst_json),
        "template_path": str(dst_tpl),
        "next_steps": [
            f"Review {dst_tpl.name}, fill in capability/description/node_mapping, then rename to {wid}.config.json when ready.",
            f"Run preflight: uv run --no-sync python -m comfyui generate --workflow {wid} --preflight",
        ],
    }
