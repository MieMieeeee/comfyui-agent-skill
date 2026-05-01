from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from comfyui.config import SKILL_ROOT, check_server, get_comfyui_url, local_config_path, save_comfyui_url
from comfyui.tools.import_workflow import import_workflow, validate_workflow_id


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
    p = argparse.ArgumentParser(
        description="Import a ComfyUI workflow JSON into assets/workflows and generate a config template."
    )
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

