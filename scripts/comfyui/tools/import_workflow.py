from __future__ import annotations

import datetime as _dt
import json
import re
import sys
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

# Sentinel returned by prompt_for_prompt_node when running non-interactively and
# no prompt node can be auto-selected. The CLI surfaces candidates + a re-run
# hint instead of blocking on stdin.
PROMPT_NODE_UNRESOLVED = "__NEEDS_PROMPT_NODE__"


class AmbiguousNodeTitleError(ValueError):
    """Raised when node_mapping points two roles at the same duplicated title.

    set_node_param matches by title and would overwrite *all* nodes sharing
    that title, silently cross-writing (e.g. positive/negative prompt). This
    is caught at import time so the maintainer can rename the nodes.
    """


def validate_workflow_id(raw: str) -> str:
    wid = (raw or "").strip().lower()
    if not wid or not _WORKFLOW_ID_RE.fullmatch(wid):
        raise ValueError("workflow_id must match ^[a-z0-9][a-z0-9_-]{0,63}$")
    return wid


def parse_prompt_node_spec(spec: str) -> tuple[str, str]:
    """Parse a ``--prompt-node "node_title:param_name"`` spec.

    Raises ValueError on malformed input (missing colon, empty parts).
    """
    if ":" not in spec:
        raise ValueError(
            '--prompt-node must be "node_title:param_name" (missing colon)'
        )
    title, param = spec.split(":", 1)
    title = title.strip()
    param = param.strip()
    if not title or not param:
        raise ValueError(
            '--prompt-node must be "node_title:param_name" (empty title or param)'
        )
    return title, param


def prompt_for_prompt_node(
    candidates: list[dict], *, interactive: bool, input_fn=input
) -> str | None:
    """Resolve which candidate node hosts the user-facing prompt.

    Returns one of:
    - ``"node_title:param_name"`` — the maintainer's interactive choice.
    - ``None`` — maintainer chose to skip (entered blank / 0).
    - :data:`PROMPT_NODE_UNRESOLVED` — non-interactive context; the CLI must
      surface candidates and a re-run hint instead of blocking on stdin.

    ``input_fn`` is injectable for testing; defaults to builtin ``input``.
    """
    if not candidates:
        return None

    if not interactive:
        # Never block on stdin in CI / subprocess / scripted contexts.
        return PROMPT_NODE_UNRESOLVED

    print(
        "\nCould not auto-detect the prompt node. Pick the node field that "
        "receives the user-facing prompt. The current value helps you tell the "
        "prompt apart from settings (e.g. sampler names, file paths):",
        file=sys.stderr,
    )
    for i, c in enumerate(candidates, 1):
        print(
            f"  {i:>2}. {c['title']}.{c['param']}  [{c['class_type']}]"
            f"  = {c.get('current_value', '?')}",
            file=sys.stderr,
        )
    print("   0. skip (resolve manually in the template later)", file=sys.stderr)

    while True:
        try:
            raw = input_fn("prompt node number (0 to skip): ").strip()
        except EOFError:
            # stdin looked like a TTY but has no data (e.g. subprocess inheriting
            # a terminal but with no interactive input). Degrade to non-interactive.
            return PROMPT_NODE_UNRESOLVED
        if raw == "" or raw == "0":
            return None
        try:
            idx = int(raw)
        except ValueError:
            print("  enter a number", file=sys.stderr)
            continue
        if 1 <= idx <= len(candidates):
            chosen = candidates[idx - 1]
            return f"{chosen['title']}:{chosen['param']}"
        print(f"  enter a number between 0 and {len(candidates)}", file=sys.stderr)


def check_ambiguous_titles(workflow_data: dict, node_mapping: dict[str, dict]) -> None:
    """Raise AmbiguousNodeTitleError if two roles target a duplicated title.

    ``workflow_data`` is the parsed API-format workflow (``{"1": {...}}``).
    ``node_mapping`` is the analyzer-produced mapping. We count how many real
    nodes share each title; if a title is claimed by >1 distinct role AND the
    workflow actually has >=2 nodes with that title, the mapping is ambiguous
    (set_node_param would cross-write them).
    """
    title_counts: dict[str, int] = {}
    for node in workflow_data.values():
        if not isinstance(node, dict):
            continue
        meta = node.get("_meta") or {}
        title = meta.get("title") or node.get("class_type", "")
        if title:
            title_counts[title] = title_counts.get(title, 0) + 1

    # Group roles by the title they target.
    roles_by_title: dict[str, list[str]] = {}
    for role, entry in node_mapping.items():
        title = entry.get("node_title")
        if not title:
            continue
        roles_by_title.setdefault(title, []).append(role)

    ambiguous: list[tuple[str, list[str], int]] = []
    for title, roles in roles_by_title.items():
        if len(roles) > 1 and title_counts.get(title, 0) > 1:
            ambiguous.append((title, sorted(roles), title_counts[title]))

    if ambiguous:
        parts = [
            f"title {t!r} targeted by roles {rs} but {n} nodes share it"
            for t, rs, n in ambiguous
        ]
        raise AmbiguousNodeTitleError(
            "node_mapping has ambiguous node titles — set_node_param matches by "
            "title and would cross-write all nodes sharing it. "
            "Rename the nodes in the workflow JSON so each has a unique title "
            "(e.g. add '(Positive Prompt)' / '(Negative Prompt)'). Details: "
            + "; ".join(parts)
        )


def _resolve_prompt_node(
    config: dict,
    workflow_data: dict,
    *,
    prompt_node: str | None,
    interactive: bool,
) -> str:
    """Ensure config has a usable prompt role; mutate config in place.

    Returns a status string for the CLI to act on:
    - ``"detected"``      — analyzer already found a prompt-like role.
    - ``"specified"``     --prompt-node was given and written into node_mapping.
    - ``"selected"``      — maintainer picked a node interactively.
    - ``"skipped"``       — maintainer chose to skip; template ships without prompt.
    - ``"unresolved"``    — non-interactive, no --prompt-node; CLI must surface a hint.
    - ``"no_candidates"`` — no string-bearing nodes found; nothing to ask.
    """
    from comfyui.tools.analyze_workflow import prompt_is_detected

    node_mapping = config["node_mapping"]

    # 1. Analyzer already detected a prompt-like role.
    if prompt_is_detected(node_mapping):
        return "detected"

    candidates = config.get("_prompt_candidates") or []

    # 2. Explicit --prompt-node wins; validate it against the discovered nodes.
    if prompt_node:
        title, param = parse_prompt_node_spec(prompt_node)
        node_mapping["prompt"] = {
            "node_title": title,
            "param": param,
            "value_type": "string",
            "required": True,
            "source": "prompt_node_flag",
        }
        return "specified"

    if not candidates:
        return "no_candidates"

    # 3. Interactively ask (or, non-interactive, surface the unresolved signal).
    choice = prompt_for_prompt_node(candidates, interactive=interactive)
    if choice is None:
        return "skipped"
    if choice == PROMPT_NODE_UNRESOLVED:
        return "unresolved"
    title, param = parse_prompt_node_spec(choice)
    node_mapping["prompt"] = {
        "node_title": title,
        "param": param,
        "value_type": "string",
        "required": True,
        "source": "interactive",
    }
    return "selected"


def import_workflow(
    *,
    src_path: Path,
    workflow_id: str | None,
    force: bool,
    into_project: bool,
    user_data_root: Path | None = None,
    project_root: Path | None = None,
    prompt_node: str | None = None,
    interactive: bool = False,
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
        prompt_status = _resolve_prompt_node(config, data, prompt_node=prompt_node, interactive=interactive)
        check_ambiguous_titles(data, config["node_mapping"])
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
        prompt_status = _resolve_prompt_node(config, data, prompt_node=prompt_node, interactive=interactive)
        check_ambiguous_titles(data, config["node_mapping"])
        dst_tpl.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    payload: dict[str, Any] = {
        "success": True,
        "workflow_id": wid,
        "workflow_path": str(dst_json),
        "template_path": str(dst_tpl),
        "prompt_status": prompt_status,
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

    # When the prompt node could not be resolved non-interactively, surface the
    # candidate nodes + a ready-to-run --prompt-node example at the top of
    # next_steps so the maintainer knows exactly how to fix it.
    if prompt_status == "unresolved":
        candidates = config.get("_prompt_candidates") or []
        cand_lines = [
            f"      - {c['title']}.{c['param']}  [{c['class_type']}]  = {c.get('current_value', '?')}"
            for c in candidates[:10]
        ]
        first = candidates[0] if candidates else None
        example = (
            f'--prompt-node "{first["title"]}:{first["param"]}"'
            if first
            else '--prompt-node "node_title:param_name"'
        )
        payload["_prompt_candidates"] = candidates
        payload["next_steps"].insert(
            0,
            "ACTION NEEDED: the prompt node could not be auto-detected. Re-run import with "
            f"{example} (or edit node_mapping.prompt in the template). Candidates (with each "
            "field's current value to help you tell the prompt apart from settings):\n"
            + "\n".join(cand_lines),
        )

    return payload
