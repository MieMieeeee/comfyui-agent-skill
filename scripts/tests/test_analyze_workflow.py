"""Tests for the workflow analyzer."""
from pathlib import Path

from comfyui.tools.analyze_workflow import analyze_workflow
from comfyui.services.workflow_config import WorkflowConfig


class TestAnalyzerBasic:
    def test_analyze_z_image_turbo(self, skill_root):
        workflow_path = skill_root / "assets" / "workflows" / "z_image_turbo.json"
        config = analyze_workflow(workflow_path)

        assert config["workflow_id"] == "z_image_turbo"
        assert config["workflow_file"] == "z_image_turbo.json"
        assert config["output_node_title"] == "Save Image"
        assert "prompt" in config["node_mapping"]
        assert "seed" in config["node_mapping"]
        assert "width" in config["node_mapping"]
        assert "height" in config["node_mapping"]

    def test_analyze_discovers_all_nodes(self, skill_root):
        workflow_path = skill_root / "assets" / "workflows" / "z_image_turbo.json"
        config = analyze_workflow(workflow_path)

        discovered = config["_discovered_nodes"]
        assert "KSampler" in discovered
        assert "Save Image" in discovered
        assert "Load Diffusion Model" in discovered
        assert len(discovered) == 9

    def test_analyze_prompt_mapping(self, skill_root):
        workflow_path = skill_root / "assets" / "workflows" / "z_image_turbo.json"
        config = analyze_workflow(workflow_path)

        prompt = config["node_mapping"]["prompt"]
        assert prompt["node_title"] == "CLIP Text Encode (Positive Prompt)"
        assert prompt["param"] == "text"
        assert prompt["required"] is True

    def test_analyze_seed_mapping(self, skill_root):
        workflow_path = skill_root / "assets" / "workflows" / "z_image_turbo.json"
        config = analyze_workflow(workflow_path)

        seed = config["node_mapping"]["seed"]
        assert seed["node_title"] == "KSampler"
        assert seed["param"] == "seed"
        assert seed["auto_random"] is True

    def test_analyze_dimensions_with_defaults(self, skill_root):
        workflow_path = skill_root / "assets" / "workflows" / "z_image_turbo.json"
        config = analyze_workflow(workflow_path)

        assert config["node_mapping"]["width"]["default"] == 832
        assert config["node_mapping"]["height"]["default"] == 1280

    def test_analyze_detects_image_input_for_klein_edit(self, skill_root):
        workflow_path = skill_root / "assets" / "workflows" / "klein_edit.json"
        config = analyze_workflow(workflow_path)
        assert config["output_kind"] == "image"
        assert config["capability"] == "image_to_image"
        assert "input_image" in config["node_mapping"]
        m = config["node_mapping"]["input_image"]
        assert m["value_type"] == "image"
        assert m["input_strategy"] == "upload"
        assert m.get("required") is True

    def test_analyze_detects_tts_inputs_and_audio_output(self, skill_root):
        workflow_path = skill_root / "assets" / "workflows" / "qwen3_tts.json"
        config = analyze_workflow(workflow_path)
        assert config["output_kind"] == "audio"
        assert config["capability"] == "text_to_speech"
        assert config["output_node_title"] == "Save Audio (MP3)"
        assert "speech_text" in config["node_mapping"]
        assert "instruct" in config["node_mapping"]
        assert config["node_mapping"]["speech_text"]["param"] == "text"
        assert config["node_mapping"]["instruct"]["param"] == "instruct"

    def test_analyze_detects_video_output_kind(self, skill_root):
        workflow_path = skill_root / "assets" / "workflows" / "ltx-23-t2v.json"
        config = analyze_workflow(workflow_path)
        assert config["output_kind"] == "video"
        assert config["capability"] == "text_to_video"
        assert config["output_node_title"] == "Video Combine (Primary MP4)"

    def test_analyze_includes_template_field_groups(self, skill_root):
        workflow_path = skill_root / "assets" / "workflows" / "z_image_turbo.json"
        config = analyze_workflow(workflow_path)
        assert "_template" in config
        assert "required_fields" in config["_template"]
        assert "optional_fields" in config["_template"]


class TestAnalyzerRoundtrip:
    def test_generated_config_loads_as_workflow_config(self, skill_root):
        workflow_path = skill_root / "assets" / "workflows" / "z_image_turbo.json"
        config = analyze_workflow(workflow_path)

        config.pop("_discovered_nodes", None)
        config.pop("_required_models", None)
        config.pop("_required_plugins", None)
        config["capability"] = "text_to_image"
        config["description"] = "Test"

        cfg = WorkflowConfig(
            workflow_id=config["workflow_id"],
            workflow_file=config["workflow_file"],
            output_node_title=config["output_node_title"],
            node_mapping=config["node_mapping"],
            capability=config["capability"],
            description=config["description"],
        )
        assert "prompt" in cfg.node_mapping
