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
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["available"] else 1


def cmd_doctor() -> int:
    import comfyui.config as config
    import comfyui.preflight as preflight
    import comfyui.services.workflow_config as workflow_config

    p = argparse.ArgumentParser(
        description="Check environment: ComfyUI availability and preflight (nodes/models) for registered workflows."
    )
    p.add_argument("--server", default=None, help="ComfyUI server URL")
    p.add_argument(
        "--workflow",
        action="append",
        default=[],
        help="Check a specific registered workflow_id (repeatable). Default: check all registered workflows.",
    )
    args = p.parse_args()

    url = args.server or get_comfyui_url()
    server = check_server(url)

    workflows_dir = config.get_workflows_dir()
    registry = workflow_config.WORKFLOW_REGISTRY

    workflow_ids = [w for w in args.workflow if w] or sorted(registry.keys())
    workflows: dict[str, dict] = {}

    for wid in workflow_ids:
        cfg = registry.get(wid)
        if cfg is None:
            workflows[wid] = {
                "success": False,
                "workflow_id": wid,
                "preflight": {
                    "server_reachable": bool(server.get("available")),
                    "missing_node_types": [],
                    "missing_models": [],
                    "warnings": [],
                },
                "error": {"code": "WORKFLOW_NOT_REGISTERED", "message": f"Workflow '{wid}' is not registered."},
            }
            continue

        wf_path = cfg.resolve_workflow_path(workflows_dir)
        if not wf_path.exists():
            workflows[wid] = {
                "success": False,
                "workflow_id": wid,
                "preflight": {
                    "server_reachable": bool(server.get("available")),
                    "missing_node_types": [],
                    "missing_models": [],
                    "warnings": [],
                },
                "error": {"code": "WORKFLOW_FILE_NOT_FOUND", "message": f"Workflow file not found: {wf_path}"},
            }
            continue

        result = preflight.preflight_registered_workflow(url, wf_path)
        workflows[wid] = preflight.build_preflight_cli_payload(wid, result)

    ok_workflows = sorted([wid for wid, payload in workflows.items() if payload.get("success") is True])
    failed_workflows = sorted([wid for wid, payload in workflows.items() if payload.get("success") is not True])
    missing_node_types = sorted(
        {
            node
            for payload in workflows.values()
            for node in (payload.get("preflight", {}).get("missing_node_types") or [])
            if isinstance(node, str)
        }
    )
    missing_models = sorted(
        {m["path"]: m for payload in workflows.values() for m in (payload.get("preflight", {}).get("missing_models") or []) if isinstance(m, dict)}.values(),
        key=lambda m: m.get("path", ""),
    )

    success = bool(server.get("available")) and len(failed_workflows) == 0
    payload = {
        "success": success,
        "server": server,
        "workflows_checked": workflow_ids,
        "workflows": workflows,
        "summary": {
            "ok_workflows": ok_workflows,
            "failed_workflows": failed_workflows,
            "missing_node_types": missing_node_types,
            "missing_models": missing_models,
        },
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if success else 1


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
            ensure_ascii=True,
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
                ensure_ascii=True,
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
        print(json.dumps({"success": False, "workflow_id": wid, "error": err}, ensure_ascii=True, indent=2))
        return 1
    except FileExistsError:
        err = {"code": "WORKFLOW_ALREADY_EXISTS", "message": f"Workflow '{wid}' already exists. Use --force to overwrite."}
        print(json.dumps({"success": False, "workflow_id": wid, "error": err}, ensure_ascii=True, indent=2))
        return 1
    except ValueError as e:
        err = {"code": "WORKFLOW_JSON_INVALID", "message": str(e)}
        print(json.dumps({"success": False, "workflow_id": wid, "error": err}, ensure_ascii=True, indent=2))
        return 1

    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0
