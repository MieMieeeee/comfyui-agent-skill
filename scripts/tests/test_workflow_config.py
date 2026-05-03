"""Tests for workflow config with node_mapping and JSON loading."""
import json
from pathlib import Path

import pytest

from comfyui.services.workflow_config import (
    ConfigError,
    WORKFLOW_REGISTRY,
    WorkflowConfig,
    load_configs_from_dir,
    Z_IMAGE_TURBO,
)


class TestNodeMapping:
    def test_z_image_turbo_has_complete_mapping(self):
        m = Z_IMAGE_TURBO.node_mapping
        assert "prompt" in m
        assert "seed" in m
        assert "width" in m
        assert "height" in m

    def test_mapping_has_required_fields(self):
        for key, entry in Z_IMAGE_TURBO.node_mapping.items():
            assert "node_title" in entry, f"mapping '{key}' missing node_title"
            assert "param" in entry, f"mapping '{key}' missing param"

    def test_prompt_mapping(self):
        m = Z_IMAGE_TURBO.node_mapping["prompt"]
        assert m["node_title"] == "CLIP Text Encode (Positive Prompt)"
        assert m["param"] == "text"
        assert m.get("required") is True

    def test_seed_mapping(self):
        m = Z_IMAGE_TURBO.node_mapping["seed"]
        assert m["node_title"] == "KSampler"
        assert m["param"] == "seed"
        assert m.get("auto_random") is True

    def test_dimensions_mapping(self):
        w = Z_IMAGE_TURBO.node_mapping["width"]
        h = Z_IMAGE_TURBO.node_mapping["height"]
        assert w["node_title"] == "EmptySD3LatentImage"
        assert w["param"] == "width"
        assert w["default"] == 832
        assert h["param"] == "height"
        assert h["default"] == 1280

    def test_optional_negative_prompt(self):
        m = Z_IMAGE_TURBO.node_mapping.get("negative_prompt")
        assert m is not None
        assert m["node_title"] == "CLIP Text Encode (Negative Prompt)"

    def test_custom_mapping(self):
        cfg = WorkflowConfig(
            workflow_id="custom",
            workflow_file="custom.json",
            output_node_title="Output",
            node_mapping={
                "prompt": {"node_title": "PromptNode", "param": "text", "required": True},
                "seed": {"node_title": "Sampler", "param": "seed", "auto_random": True},
            },
        )
        assert cfg.node_mapping["prompt"]["node_title"] == "PromptNode"
        assert cfg.node_mapping["seed"]["param"] == "seed"


class TestJsonConfig:
    def test_z_image_turbo_config_json_exists(self, skill_root):
        config_path = skill_root / "assets" / "workflows" / "z_image_turbo.config.json"
        assert config_path.exists()

    def test_config_json_is_valid(self, skill_root):
        config_path = skill_root / "assets" / "workflows" / "z_image_turbo.config.json"
        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert data["workflow_id"] == "z_image_turbo"
        assert "node_mapping" in data
        assert "output_node_title" in data

    def test_config_json_matches_runtime_config(self, skill_root):
        config_path = skill_root / "assets" / "workflows" / "z_image_turbo.config.json"
        data = json.loads(config_path.read_text(encoding="utf-8"))
        # The JSON config should have the same mapping keys as the runtime config
        for key in ["prompt", "seed", "width", "height"]:
            assert key in data["node_mapping"], f"Missing mapping key: {key}"

    def test_load_config_from_json(self, skill_root):
        config_path = skill_root / "assets" / "workflows" / "z_image_turbo.config.json"
        cfg = WorkflowConfig.from_json_file(config_path)
        assert cfg.workflow_id == "z_image_turbo"
        assert "prompt" in cfg.node_mapping
        assert cfg.output_node_title == "Save Image"

    def test_load_configs_from_dir(self, skill_root):
        workflows_dir = skill_root / "assets" / "workflows"
        registry = load_configs_from_dir(workflows_dir)
        assert "z_image_turbo" in registry
        assert registry["z_image_turbo"].capability == "text_to_image"

    def test_qwen3_tts_registry_and_paths(self, skill_root):
        cfg = WORKFLOW_REGISTRY.get("qwen3_tts")
        assert cfg is not None
        assert cfg.output_kind == "audio"
        assert cfg.output_node_title == "Save Audio (MP3)"
        assert cfg.capability == "text_to_speech"
        wf_path = cfg.resolve_workflow_path(skill_root / "assets" / "workflows")
        assert wf_path.name == "qwen3_tts.json"
        assert wf_path.exists()

    def test_qwen3_tts_node_mapping(self):
        cfg = WORKFLOW_REGISTRY["qwen3_tts"]
        assert cfg.node_mapping["speech_text"]["param"] == "text"
        assert cfg.node_mapping["instruct"]["param"] == "instruct"

    def test_ltx_t2v_cli_dimensions_and_presets(self, skill_root):
        cfg = WORKFLOW_REGISTRY["ltx_23_t2v_distilled"]
        assert cfg.size_strategy != "workflow_managed"
        assert cfg.node_mapping["width"]["node_title"] == "EmptyImage"
        assert cfg.node_mapping["width"]["default"] == 768
        assert cfg.node_mapping["height"]["default"] == 512
        assert cfg.resolution_presets["landscape_fhd"]["width"] == 1920
        assert cfg.default_resolution == "landscape_fast"

    def test_ltx_i2v_dimensions_follow_upload_no_mapping(self, skill_root):
        cfg = WORKFLOW_REGISTRY["ltx_23_i2v_distilled"]
        assert "width" not in cfg.node_mapping
        assert "height" not in cfg.node_mapping
        assert cfg.resolution_presets == {}
        assert "upload" in cfg.description.lower() or "上传" in cfg.description

    def test_qwen_image_defaults_and_presets(self, skill_root):
        cfg = WORKFLOW_REGISTRY["qwen_image_2512_4step"]
        assert cfg.node_mapping["width"]["default"] == 512
        assert cfg.node_mapping["height"]["default"] == 768
        assert cfg.resolution_presets["portrait_hd"]["height"] == 1280
        assert cfg.default_resolution == "portrait_fast"

    def test_to_json_includes_resolution_presets_when_non_empty(self):
        cfg = WorkflowConfig(
            workflow_id="preset_test",
            workflow_file="preset_test.json",
            output_node_title="Out",
            node_mapping={
                "prompt": {"node_title": "P", "param": "text", "required": True},
            },
            resolution_presets={
                "p1": {"width": 100, "height": 200, "label": "small"},
            },
            default_resolution="p1",
        )
        raw = cfg.to_json()
        data = json.loads(raw)
        assert data["resolution_presets"]["p1"]["width"] == 100
        assert data["default_resolution"] == "p1"

    def test_to_json_omits_empty_presets(self):
        cfg = WorkflowConfig(
            workflow_id="no_preset",
            workflow_file="no.json",
            output_node_title="Out",
            node_mapping={"prompt": {"node_title": "P", "param": "text", "required": True}},
        )
        data = json.loads(cfg.to_json())
        assert "resolution_presets" not in data
        assert "default_resolution" not in data

    def test_from_json_presets_survive_load(self, skill_root):
        cfg = WORKFLOW_REGISTRY["ltx_23_t2v_distilled"]
        path = skill_root / "assets" / "workflows" / "ltx_23_t2v_distilled.config.json"
        loaded = WorkflowConfig.from_json_file(path)
        assert loaded.resolution_presets["landscape_hd"]["width"] == 1280
        assert loaded.default_resolution == "landscape_fast"

    def test_to_json_roundtrip(self):
        cfg = WorkflowConfig(
            workflow_id="test",
            workflow_file="test.json",
            output_node_title="Output",
            node_mapping={
                "prompt": {"node_title": "P", "param": "text", "required": True},
            },
        )
        json_str = cfg.to_json()
        data = json.loads(json_str)
        assert data["workflow_id"] == "test"
        assert data["node_mapping"]["prompt"]["node_title"] == "P"


class TestBadConfig:
    """Tests for invalid / incomplete config files."""

    def test_missing_required_field_workflow_id(self, tmp_path):
        config = tmp_path / "bad.config.json"
        config.write_text(json.dumps({"workflow_file": "x.json", "output_node_title": "Out"}))
        with pytest.raises(ConfigError, match="workflow_id"):
            WorkflowConfig.from_json_file(config)

    def test_missing_required_field_output_node_title(self, tmp_path):
        config = tmp_path / "bad.config.json"
        config.write_text(json.dumps({"workflow_id": "x", "workflow_file": "x.json"}))
        with pytest.raises(ConfigError, match="output_node_title"):
            WorkflowConfig.from_json_file(config)

    def test_invalid_json(self, tmp_path):
        config = tmp_path / "bad.config.json"
        config.write_text("{invalid json", encoding="utf-8")
        with pytest.raises(ConfigError, match="Invalid JSON"):
            WorkflowConfig.from_json_file(config)

    def test_nonexistent_file(self, tmp_path):
        config = tmp_path / "nope.config.json"
        with pytest.raises(ConfigError, match="Cannot read"):
            WorkflowConfig.from_json_file(config)

    def test_empty_node_mapping(self, tmp_path):
        config = tmp_path / "empty.config.json"
        config.write_text(json.dumps({
            "workflow_id": "empty",
            "workflow_file": "empty.json",
            "output_node_title": "Out",
            "node_mapping": {},
        }))
        cfg = WorkflowConfig.from_json_file(config)
        assert cfg.node_mapping == {}

    def test_missing_prompt_mapping_detected_by_executor(self, tmp_path):
        """Executor should fail when workflow has no string inputs configured."""
        from comfyui.services.executor import execute_workflow
        wf = tmp_path / "assets" / "workflows" / "x.json"
        wf.parent.mkdir(parents=True, exist_ok=True)
        wf.write_text("{}", encoding="utf-8")
        bad_config = WorkflowConfig(
            workflow_id="no_prompt",
            workflow_file="x.json",
            output_node_title="Out",
            node_mapping={},
        )
        result = execute_workflow(config=bad_config, prompt="test", skill_root=tmp_path)
        assert result.success is False
        assert result.error["code"] == "MAPPING_NOT_FOUND"

    def test_config_json_has_value_type(self, skill_root):
        config_path = skill_root / "assets" / "workflows" / "z_image_turbo.config.json"
        data = json.loads(config_path.read_text(encoding="utf-8"))
        for key, entry in data["node_mapping"].items():
            assert "value_type" in entry, f"mapping '{key}' missing value_type"

    def test_load_configs_from_dir_propagates_config_error(self, tmp_path):
        bad = tmp_path / "bad.config.json"
        bad.write_text("{broken", encoding="utf-8")
        with pytest.raises(ConfigError):
            load_configs_from_dir(tmp_path)
