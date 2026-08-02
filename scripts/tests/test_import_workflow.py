import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = (SKILL_ROOT / "scripts").resolve()


def _run_module(*args: str, extra_env: dict | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(SCRIPTS_DIR), **(extra_env or {})}
    return subprocess.run(
        [sys.executable, "-m", "comfyui", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or SKILL_ROOT),
        env=env,
    )


def _write_min_workflow(path: Path) -> None:
    wf = {
        "1": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "a cat"},
            "_meta": {"title": "CLIP Text Encode (Positive Prompt)"},
        },
        "2": {
            "class_type": "SaveImage",
            "inputs": {},
            "_meta": {"title": "Save Image"},
        },
    }
    path.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")


class TestImportWorkflow:
    def test_import_creates_workflow_and_template(self, tmp_path: Path):
        src = tmp_path / "my_workflow.json"
        _write_min_workflow(src)

        r = _run_module(
            "import-workflow",
            str(src),
            "--skill-root",
            str(tmp_path),
        )
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        assert data["success"] is True
        assert data["workflow_id"] == "my_workflow"

        dst_json = tmp_path / "custom_workflows" / "my_workflow" / "workflow.json"
        dst_tpl = tmp_path / "custom_workflows" / "my_workflow" / "workflow.config.template.json"
        assert dst_json.exists()
        assert dst_tpl.exists()
        tpl = json.loads(dst_tpl.read_text(encoding="utf-8"))
        assert tpl["workflow_id"] == "my_workflow"
        assert tpl["workflow_file"] == "my_workflow/workflow.json"

    def test_import_refuses_overwrite_without_force(self, tmp_path: Path):
        src = tmp_path / "wf.json"
        _write_min_workflow(src)

        r1 = _run_module("import-workflow", str(src), "--skill-root", str(tmp_path))
        assert r1.returncode == 0

        r2 = _run_module("import-workflow", str(src), "--skill-root", str(tmp_path))
        assert r2.returncode != 0
        data = json.loads(r2.stdout)
        assert data["success"] is False
        assert data["error"]["code"] == "WORKFLOW_ALREADY_EXISTS"

    def test_import_rejects_invalid_json(self, tmp_path: Path):
        src = tmp_path / "bad.json"
        src.write_text("{not json", encoding="utf-8")

        r = _run_module("import-workflow", str(src), "--skill-root", str(tmp_path))
        assert r.returncode != 0
        data = json.loads(r.stdout)
        assert data["success"] is False
        assert data["error"]["code"] == "WORKFLOW_JSON_INVALID"

    @pytest.mark.parametrize("bad_id", ["Bad Id", "../x", "a/b", ""])
    def test_import_rejects_invalid_workflow_id(self, tmp_path: Path, bad_id: str):
        src = tmp_path / "wf.json"
        _write_min_workflow(src)

        r = _run_module(
            "import-workflow",
            str(src),
            "--id",
            bad_id,
            "--skill-root",
            str(tmp_path),
        )
        assert r.returncode != 0
        data = json.loads(r.stdout)
        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_WORKFLOW_ID"

    def test_import_rejects_builtin_id_conflict(self, tmp_path: Path):
        src = tmp_path / "wf.json"
        _write_min_workflow(src)

        r = _run_module(
            "import-workflow",
            str(src),
            "--id",
            "z_image_turbo",
            "--skill-root",
            str(tmp_path),
        )
        assert r.returncode != 0
        data = json.loads(r.stdout)
        assert data["success"] is False
        assert data["error"]["code"] == "WORKFLOW_ID_CONFLICTS_WITH_BUILTIN"


class TestImportWorkflowFormatGuard:
    """Import must refuse non-API input with an actionable error, not crash analyze."""

    def _write_ui_workflow(self, path: Path) -> None:
        # UI/Save format: {nodes: [...], links: [...]} (litegraph graph).
        ui = {
            "id": 4,
            "nodes": [
                {"id": 1, "type": "SaveImage", "title": "Save Image", "widgets_values": []},
            ],
            "links": [[1, 2, 0, 1, 0, "IMAGE"]],
        }
        path.write_text(json.dumps(ui, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_import_rejects_ui_format(self, tmp_path: Path):
        src = tmp_path / "ui_workflow.json"
        self._write_ui_workflow(src)

        r = _run_module("import-workflow", str(src), "--skill-root", str(tmp_path))
        assert r.returncode != 0, r.stderr
        data = json.loads(r.stdout)
        assert data["success"] is False
        assert data["error"]["code"] == "WORKFLOW_NOT_API_FORMAT"
        # The message must steer the user toward the fix.
        msg = data["error"]["message"]
        assert "Save (API)" in msg
        assert "convert-ui" in msg

    def test_import_rejects_unknown_format(self, tmp_path: Path):
        src = tmp_path / "weird.json"
        src.write_text(json.dumps({"random": "stuff"}), encoding="utf-8")

        r = _run_module("import-workflow", str(src), "--skill-root", str(tmp_path))
        assert r.returncode != 0
        data = json.loads(r.stdout)
        assert data["error"]["code"] == "WORKFLOW_NOT_API_FORMAT"


class TestImportPromptNodeResolution:
    """When the analyzer cannot detect the prompt node, import must surface it."""

    @staticmethod
    def _write_no_prompt_workflow(path: Path) -> None:
        # API format, but prompt lives in a non-CLIP string node so the
        # analyzer's CLIP/encode heuristic misses it.
        wf = {
            "1": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
                  "_meta": {"title": "Empty Latent Image"}},
            "2": {"class_type": "KSampler", "inputs": {"seed": 1, "cfg": 1, "steps": 8, "denoise": 1,
                  "sampler_name": "euler", "scheduler": "simple"}, "_meta": {"title": "KSampler"}},
            "3": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": "a user prompt"},
                  "_meta": {"title": "Text String (User Prompt)"}},
            "4": {"class_type": "SaveImage", "inputs": {"filename_prefix": "x"}, "_meta": {"title": "Save Image"}},
        }
        path.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_no_prompt_noninteractive_surfaces_candidates(self, tmp_path: Path):
        src = tmp_path / "no_prompt.json"
        self._write_no_prompt_workflow(src)

        r = _run_module("import-workflow", str(src), "--skill-root", str(tmp_path), "--no-interactive")
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        assert data["success"] is True
        assert data["prompt_status"] == "unresolved"
        # next_steps must point the maintainer at --prompt-node with the candidate listed.
        assert "--prompt-node" in data["next_steps"][0]
        assert "Text String (User Prompt)" in data["next_steps"][0]
        assert any(c["title"] == "Text String (User Prompt)" for c in data.get("_prompt_candidates", []))

    def test_prompt_node_flag_writes_mapping(self, tmp_path: Path):
        src = tmp_path / "no_prompt.json"
        self._write_no_prompt_workflow(src)

        r = _run_module(
            "import-workflow", str(src), "--skill-root", str(tmp_path),
            "--prompt-node", "Text String (User Prompt):value",
        )
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        assert data["prompt_status"] == "specified"
        tpl = tmp_path / "custom_workflows" / "no_prompt" / "workflow.config.template.json"
        cfg = json.loads(tpl.read_text(encoding="utf-8"))
        prompt = cfg["node_mapping"]["prompt"]
        assert prompt["node_title"] == "Text String (User Prompt)"
        assert prompt["param"] == "value"
        assert prompt["required"] is True

    def test_prompt_node_flag_rejects_malformed_spec(self, tmp_path: Path):
        src = tmp_path / "wf.json"
        _write_min_workflow(src)
        r = _run_module(
            "import-workflow", str(src), "--skill-root", str(tmp_path),
            "--prompt-node", "no-colon-here",
        )
        assert r.returncode != 0
        data = json.loads(r.stdout)
        assert data["error"]["code"] == "INVALID_PROMPT_NODE"


class TestImportAmbiguousTitles:
    """Two node_mapping roles pointing at a duplicated title must be caught."""

    @staticmethod
    def _write_dup_title_workflow(path: Path) -> None:
        # Two CLIPTextEncode nodes share the identical title (the Anima problem).
        wf = {
            "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "positive"},
                  "_meta": {"title": "CLIP Text Encode (Prompt)"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "negative"},
                  "_meta": {"title": "CLIP Text Encode (Prompt)"}},
            "3": {"class_type": "SaveImage", "inputs": {}, "_meta": {"title": "Save Image"}},
        }
        path.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_ambiguous_titles_rejected(self, tmp_path: Path):
        src = tmp_path / "dup.json"
        self._write_dup_title_workflow(src)

        r = _run_module("import-workflow", str(src), "--skill-root", str(tmp_path), "--no-interactive")
        assert r.returncode != 0
        data = json.loads(r.stdout)
        assert data["error"]["code"] == "AMBIGUOUS_NODE_TITLE"
        assert "rename" in data["error"]["message"].lower()


class TestImportPromptNodeInteractive:
    """Interactive prompt-node selection via injectable input_fn (no real stdin)."""

    def test_interactive_selection_writes_prompt(self):
        from comfyui.tools.import_workflow import prompt_for_prompt_node

        candidates = [
            {"title": "Text String (User Prompt)", "class_type": "PrimitiveStringMultiline",
             "param": "value", "current_value": "a cat on a sofa"},
            {"title": "System Prompt", "class_type": "PrimitiveStringMultiline",
             "param": "value", "current_value": "You are an expert..."},
        ]
        choice = prompt_for_prompt_node(candidates, interactive=True, input_fn=lambda _: "1")
        assert choice == "Text String (User Prompt):value"

    def test_interactive_skip_returns_none(self):
        from comfyui.tools.import_workflow import prompt_for_prompt_node

        candidates = [{"title": "X", "class_type": "T", "param": "p", "current_value": "v"}]
        assert prompt_for_prompt_node(candidates, interactive=True, input_fn=lambda _: "0") is None
        assert prompt_for_prompt_node(candidates, interactive=True, input_fn=lambda _: "") is None

    def test_noninteractive_returns_unresolved_sentinel(self):
        from comfyui.tools.import_workflow import prompt_for_prompt_node, PROMPT_NODE_UNRESOLVED

        candidates = [{"title": "X", "class_type": "T", "param": "p", "current_value": "v"}]
        assert prompt_for_prompt_node(candidates, interactive=False) == PROMPT_NODE_UNRESOLVED

    def test_no_candidates_returns_none(self):
        from comfyui.tools.import_workflow import prompt_for_prompt_node

        assert prompt_for_prompt_node([], interactive=True) is None
