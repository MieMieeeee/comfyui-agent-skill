from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from comfyui.config import SKILL_ROOT, check_server, get_comfyui_url
from comfyui.preflight import build_preflight_cli_payload
from comfyui.services.executor import execute_workflow
from comfyui.services.workflow_config import WorkflowConfig


@dataclass(frozen=True)
class ValidateCase:
    workflow_id: str
    prompt: str
    text_inputs: dict[str, str]
    input_images: dict[str, str]
    width: int | None = None
    height: int | None = None


def _cases() -> dict[str, ValidateCase]:
    return {
        "z_image_turbo": ValidateCase(
            workflow_id="z_image_turbo",
            prompt="年轻女生撑着透明伞，坐在草地上，肖像构图，柔和自然光，细节清晰，写实摄影风格",
            text_inputs={},
            input_images={},
        ),
        "z_image_turbo_reference": ValidateCase(
            workflow_id="z_image_turbo",
            prompt="Photorealistic, ultra-detailed portrait of a young woman with a short messy dark brown bob, wearing a chunky oatmeal-colored ribbed-knit scarf and an oversized cardigan with bold horizontal stripes in navy blue, mustard yellow, and teal green. She is running through a sunlit park path, dynamic motion, hair flowing with movement, soft golden hour light, shallow depth of field, 85mm f/2.0, natural and energetic expression",
            text_inputs={},
            input_images={},
        ),
        "qwen_image_2512_4step": ValidateCase(
            workflow_id="qwen_image_2512_4step",
            prompt="A watercolor style poster. Centered large Chinese characters: 五一节快乐. Clean composition, soft colors, textured paper, high quality.",
            text_inputs={},
            input_images={},
        ),
        "klein_edit": ValidateCase(
            workflow_id="klein_edit",
            prompt="只把人物的衣服换成连衣裙，保持脸部、发型、姿势、背景、光照与构图不变，真实自然",
            text_inputs={},
            input_images={"input_image": "assets/input/person.png"},
        ),
        "ltx-23-t2v": ValidateCase(
            workflow_id="ltx-23-t2v",
            prompt="一只猫懒洋洋地打哈欠，轻微镜头推近，柔和光线，真实自然运动，稳定画面",
            text_inputs={},
            input_images={},
        ),
        "ltx-23-i2v": ValidateCase(
            workflow_id="ltx-23-i2v",
            prompt="A cinematic close-up portrait of a young woman with a tousled chin-length bob, wearing a chunky-knit taupe scarf and an oversized striped cardigan in navy, teal, and mustard. She gazes upward with a melancholic, contemplative expression, soft diffused twilight light illuminating her face from the upper left. Gentle breeze moves her hair. The camera slowly drifts laterally with subtle breathing motion. Background is a soft bokeh of deep blue evening sky and distant hazy hills. Shallow depth of field, atmospheric film grain, quiet and emotional mood.",
            text_inputs={},
            input_images={"input_image": "assets/input/person.png"},
        ),
        "qwen3_tts": ValidateCase(
            workflow_id="qwen3_tts",
            prompt="",
            text_inputs={
                "speech_text": "谢谢你一直陪伴我到现在。",
                "instruct": "模拟御姐角色：成熟自信、略带温柔，吐字清晰，语速适中，情绪真诚克制。",
            },
            input_images={},
        ),
        "ace_step_15_music": ValidateCase(
            workflow_id="ace_step_15_music",
            prompt="gentle piano ambient, soft warm pads, slow tempo, night writing mood, calm, quiet, slightly healing, minimal, smooth reverb",
            text_inputs={},
            input_images={},
        ),
    }


def _resolve_case_input_images(skill_root: Path, cfg: WorkflowConfig, case: ValidateCase) -> tuple[dict[str, Path], dict[str, Any] | None]:
    if not case.input_images:
        return {}, None
    resolved: dict[str, Path] = {}
    for role, rel in case.input_images.items():
        p = (skill_root / rel).resolve()
        if not p.exists():
            err = {"code": "VALIDATE_INPUT_NOT_FOUND", "message": f"Example input image not found: {p}"}
            return {}, err
        resolved[role] = p
    for role, entry in cfg.node_mapping.items():
        if entry.get("value_type") == "image" and entry.get("required") and role not in resolved:
            err = {"code": "VALIDATE_INPUT_MISSING", "message": f"Missing required input image role: {role}"}
            return {}, err
    return resolved, None


def cmd_validate() -> int:
    import comfyui.config as config
    import comfyui.preflight as preflight
    import comfyui.services.workflow_config as workflow_config

    p = argparse.ArgumentParser(
        description="Validate registered workflows with built-in example inputs. Default: preflight only; add --run to execute.",
    )
    p.add_argument("--server", default=None, help="ComfyUI server URL")
    p.add_argument("--workflow", action="append", default=[], help="Validate a specific workflow_id (repeatable).")
    p.add_argument("--run", action="store_true", help="Execute each workflow once using built-in example inputs.")
    p.add_argument("--timeout-s", type=float, default=1800.0, help="Per-workflow execution timeout when using --run.")
    p.add_argument("--output", default=None, help="Optional output directory for generated artifacts (only for --run).")
    args = p.parse_args()

    url = args.server or get_comfyui_url()
    server = check_server(url)
    workflows_dir = config.get_workflows_dir()

    registry = workflow_config.WORKFLOW_REGISTRY
    workflow_ids = [w for w in args.workflow if w] or sorted(registry.keys())
    cases = _cases()

    workflows: dict[str, dict[str, Any]] = {}
    for wid in workflow_ids:
        cfg = registry.get(wid)
        if cfg is None:
            workflows[wid] = {
                "success": False,
                "workflow_id": wid,
                "preflight": {"server_reachable": bool(server.get("available")), "missing_node_types": [], "missing_models": [], "warnings": []},
                "error": {"code": "WORKFLOW_NOT_REGISTERED", "message": f"Workflow '{wid}' is not registered."},
            }
            continue

        case = cases.get(wid)
        if case is None:
            workflows[wid] = {
                "success": False,
                "workflow_id": wid,
                "preflight": {"server_reachable": bool(server.get("available")), "missing_node_types": [], "missing_models": [], "warnings": []},
                "error": {"code": "VALIDATE_CASE_MISSING", "message": f"No built-in validate case for workflow '{wid}'."},
            }
            continue

        wf_path = cfg.resolve_workflow_path(workflows_dir)
        if not wf_path.exists():
            workflows[wid] = {
                "success": False,
                "workflow_id": wid,
                "preflight": {"server_reachable": bool(server.get("available")), "missing_node_types": [], "missing_models": [], "warnings": []},
                "error": {"code": "WORKFLOW_FILE_NOT_FOUND", "message": f"Workflow file not found: {wf_path}"},
            }
            continue

        pre = preflight.preflight_registered_workflow(url, wf_path)
        payload = build_preflight_cli_payload(wid, pre)
        payload["example"] = {
            "workflow_id": case.workflow_id,
            "prompt": case.prompt,
            "text_inputs": case.text_inputs,
            "input_images": case.input_images,
            "width": case.width,
            "height": case.height,
        }

        if args.run:
            if payload.get("success") is not True:
                payload["run"] = {
                    "attempted": False,
                    "success": False,
                    "error": {"code": "PREFLIGHT_FAILED", "message": "Preflight failed; run skipped."},
                }
            else:
                input_images, img_err = _resolve_case_input_images(SKILL_ROOT, cfg, case)
                if img_err is not None:
                    payload["run"] = {"attempted": False, "success": False, "error": img_err}
                    payload["success"] = False
                else:
                    out_root = Path(args.output).expanduser().resolve() if args.output else None
                    result = execute_workflow(
                        cfg,
                        case.prompt,
                        skill_root=SKILL_ROOT,
                        server_url=url,
                        results_dir=out_root,
                        output_subdir=Path("validate") / wid,
                        input_images=input_images,
                        width=case.width,
                        height=case.height,
                        text_inputs=case.text_inputs,
                        execution_timeout_s=float(args.timeout_s) if args.timeout_s else None,
                    )
                    files_ok = bool(result.outputs) and all(Path(o["path"]).exists() for o in (result.outputs or []))
                    run_success = bool(result.success) and files_ok
                    payload["run"] = {
                        "attempted": True,
                        "success": run_success,
                        "result": result.to_dict(),
                        "files_ok": files_ok,
                    }
                    if not run_success:
                        payload["success"] = False

        workflows[wid] = payload

    ok_workflows = sorted([wid for wid, payload in workflows.items() if payload.get("success") is True])
    failed_workflows = sorted([wid for wid, payload in workflows.items() if payload.get("success") is not True])
    missing_node_types = sorted(
        {node for payload in workflows.values() for node in (payload.get("preflight", {}).get("missing_node_types") or []) if isinstance(node, str)}
    )
    missing_models = sorted(
        {m["path"]: m for payload in workflows.values() for m in (payload.get("preflight", {}).get("missing_models") or []) if isinstance(m, dict)}.values(),
        key=lambda m: m.get("path", ""),
    )

    success = bool(server.get("available")) and len(failed_workflows) == 0
    out = {
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
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if success else 1
