"""Tests for workflow config data structure."""
import pytest

from comfyui.services.workflow_config import WorkflowConfig, Z_IMAGE_TURBO


class TestWorkflowConfig:
    def test_z_image_turbo_has_required_fields(self):
        cfg = Z_IMAGE_TURBO
        assert cfg.workflow_id == "z_image_turbo"
        assert cfg.workflow_file == "z_image_turbo.json"
        assert cfg.output_node_title == "Save Image"
        assert cfg.positive_prompt_node == "CLIP Text Encode (Positive Prompt)"
        assert cfg.positive_prompt_param == "text"

    def test_workflow_resolves_path(self, skill_root):
        cfg = Z_IMAGE_TURBO
        resolved = cfg.resolve_workflow_path(skill_root)
        assert resolved.exists()
        assert resolved.name == "z_image_turbo.json"

    def test_default_dimensions(self):
        cfg = Z_IMAGE_TURBO
        assert cfg.default_width == 832
        assert cfg.default_height == 1280

    def test_config_is_dataclass(self):
        cfg = WorkflowConfig(
            workflow_id="test_wf",
            workflow_file="test.json",
            output_node_title="Output",
            positive_prompt_node="Prompt",
        )
        assert cfg.workflow_id == "test_wf"
        assert cfg.default_width == 832
        assert cfg.default_height == 1280


class TestWorkflowConfigCapabilityFields:
    """Test the capability-oriented fields on WorkflowConfig."""

    def test_z_image_turbo_has_capability(self):
        assert Z_IMAGE_TURBO.capability == "text_to_image"

    def test_z_image_turbo_has_description(self):
        assert isinstance(Z_IMAGE_TURBO.description, str)
        assert len(Z_IMAGE_TURBO.description) > 0

    def test_z_image_turbo_input_schema_has_prompt(self):
        schema = Z_IMAGE_TURBO.input_schema
        assert "prompt" in schema
        assert schema["prompt"]["type"] == "string"
        assert schema["prompt"]["required"] is True

    def test_z_image_turbo_defaults(self):
        defaults = Z_IMAGE_TURBO.defaults
        assert defaults["width"] == 832
        assert defaults["height"] == 1280

    def test_custom_config_with_capability_fields(self):
        cfg = WorkflowConfig(
            workflow_id="img2img",
            workflow_file="img2img.json",
            output_node_title="Save Image",
            positive_prompt_node="Prompt",
            capability="image_to_image",
            description="Image to image transformation",
            input_schema={"prompt": {"type": "string", "required": True}, "image": {"type": "image", "required": True}},
            defaults={"width": 1024, "height": 1024, "denoise": 0.75},
        )
        assert cfg.capability == "image_to_image"
        assert cfg.description == "Image to image transformation"
        assert "image" in cfg.input_schema
        assert cfg.defaults["denoise"] == 0.75

    def test_capability_defaults_to_text_to_image(self):
        cfg = WorkflowConfig(
            workflow_id="test",
            workflow_file="test.json",
            output_node_title="Output",
            positive_prompt_node="Prompt",
        )
        assert cfg.capability == "text_to_image"
