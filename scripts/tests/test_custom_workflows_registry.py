import json
import importlib
from pathlib import Path

import pytest


def _write_min_config(path: Path, workflow_id: str, workflow_file: str) -> None:
    cfg = {
        "workflow_id": workflow_id,
        "workflow_file": workflow_file,
        "output_node_title": "Save Image",
        "capability": "text_to_image",
        "description": "Test",
        "output_kind": "image",
        "node_mapping": {"prompt": {"node_title": "X", "param": "text", "value_type": "string", "required": True}},
    }
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


class TestCustomWorkflowRegistry:
    def test_get_custom_workflows_dir_uses_user_data_root_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("COMFYUI_SKILL_USER_DATA_ROOT", str(tmp_path))
        from comfyui.config import get_custom_workflows_dir

        assert get_custom_workflows_dir() == tmp_path / "custom_workflows"

    def test_template_is_not_loaded_as_registered(self, tmp_path, monkeypatch):
        monkeypatch.setenv("COMFYUI_SKILL_USER_DATA_ROOT", str(tmp_path))
        user_root = tmp_path / "custom_workflows" / "u1"
        user_root.mkdir(parents=True, exist_ok=True)
        tpl = user_root / "workflow.config.template.json"
        _write_min_config(tpl, "u1", "u1/workflow.json")

        import comfyui.services.workflow_config as wc

        importlib.reload(wc)
        assert "u1" not in wc.WORKFLOW_REGISTRY

    def test_user_workflow_is_loaded_when_activated(self, tmp_path, monkeypatch):
        monkeypatch.setenv("COMFYUI_SKILL_USER_DATA_ROOT", str(tmp_path))
        user_root = tmp_path / "custom_workflows" / "u2"
        user_root.mkdir(parents=True, exist_ok=True)
        cfg_path = user_root / "workflow.config.json"
        _write_min_config(cfg_path, "u2", "u2/workflow.json")

        import comfyui.services.workflow_config as wc

        importlib.reload(wc)
        assert "u2" in wc.WORKFLOW_REGISTRY

    def test_user_workflow_id_conflict_is_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setenv("COMFYUI_SKILL_USER_DATA_ROOT", str(tmp_path))
        user_root = tmp_path / "custom_workflows" / "z_image_turbo"
        user_root.mkdir(parents=True, exist_ok=True)
        cfg_path = user_root / "workflow.config.json"
        _write_min_config(cfg_path, "z_image_turbo", "z_image_turbo/workflow.json")

        import comfyui.services.workflow_config as wc

        importlib.reload(wc)
        assert "z_image_turbo" in wc.WORKFLOW_REGISTRY
        assert any(e.get("code") == "USER_WORKFLOW_ID_CONFLICTS_WITH_BUILTIN" for e in wc.WORKFLOW_REGISTRY_ERRORS)

    def test_schema_version_is_optional(self, tmp_path, monkeypatch):
        monkeypatch.setenv("COMFYUI_SKILL_USER_DATA_ROOT", str(tmp_path))
        user_root = tmp_path / "custom_workflows" / "u3"
        user_root.mkdir(parents=True, exist_ok=True)
        cfg_path = user_root / "workflow.config.json"
        _write_min_config(cfg_path, "u3", "u3/workflow.json")

        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        raw.pop("schema_version", None)
        cfg_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

        import comfyui.services.workflow_config as wc

        importlib.reload(wc)
        assert "u3" in wc.WORKFLOW_REGISTRY

    def test_user_registry_scan_error_does_not_block_loading(self, tmp_path, monkeypatch):
        monkeypatch.setenv("COMFYUI_SKILL_USER_DATA_ROOT", str(tmp_path))
        custom_dir = tmp_path / "custom_workflows"
        custom_dir.mkdir(parents=True, exist_ok=True)

        import comfyui.services.workflow_config as wc

        def _boom(_p: Path) -> list[Path]:
            raise OSError("boom")

        monkeypatch.setattr(wc, "_iter_user_workflow_config_files", _boom)
        reg, errors = wc.load_user_configs_from_dir(custom_dir, builtin_ids=set())
        assert reg == {}
        assert any(e.get("code") == "USER_WORKFLOW_REGISTRY_UNAVAILABLE" for e in errors)
