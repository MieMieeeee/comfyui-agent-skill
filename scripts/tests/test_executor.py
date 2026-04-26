"""Tests for the generic workflow executor."""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from comfyui.models.result import GenerationResult
from comfyui.services.executor import execute_workflow
from comfyui.services.workflow_config import WorkflowConfig, Z_IMAGE_TURBO


def _make_mock_api(
    prompt_id="test-123",
    history=None,
    image_data=b"\x89PNG fake data",
    queue_side_effect=None,
):
    mock_api = MagicMock()
    mock_api.queue_prompt_and_wait = AsyncMock(return_value=prompt_id)
    if queue_side_effect:
        mock_api.queue_prompt_and_wait = AsyncMock(side_effect=queue_side_effect)
    mock_api.get_history.return_value = history or {
        prompt_id: {
            "outputs": {
                "9": {
                    "images": [{"filename": "image.png", "subfolder": "", "type": "output"}]
                }
            }
        }
    }
    mock_api.get_image.return_value = image_data
    return mock_api


class TestExecuteWorkflowValidation:
    def test_rejects_empty_prompt(self, skill_root):
        result = execute_workflow(config=Z_IMAGE_TURBO, prompt="", skill_root=skill_root)
        assert result.success is False
        assert result.error["code"] == "EMPTY_PROMPT"

    def test_rejects_whitespace_prompt(self, skill_root):
        result = execute_workflow(config=Z_IMAGE_TURBO, prompt="   \n\t  ", skill_root=skill_root)
        assert result.success is False
        assert result.error["code"] == "EMPTY_PROMPT"

    def test_rejects_missing_workflow_file(self, tmp_path):
        bad_config = WorkflowConfig(
            workflow_id="nonexistent",
            workflow_file="does_not_exist.json",
            output_node_title="Save Image",
            node_mapping={
                "prompt": {"node_title": "Prompt", "param": "text", "required": True},
            },
        )
        result = execute_workflow(config=bad_config, prompt="a test prompt", skill_root=tmp_path)
        assert result.success is False
        assert result.error["code"] == "WORKFLOW_FILE_NOT_FOUND"


class TestExecuteWorkflowSuccess:
    @patch("comfyui.services.executor.ComfyApiWrapper")
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_returns_success_result(self, MockWF, MockAPI, skill_root):
        mock_wf_instance = MagicMock()
        mock_wf_instance.get_node_id.return_value = "9"
        MockWF.return_value = mock_wf_instance
        MockAPI.return_value = _make_mock_api(prompt_id="test-123")

        result = execute_workflow(
            config=Z_IMAGE_TURBO,
            prompt="a cute cat",
            skill_root=skill_root,
            results_dir=skill_root / "results" / "test",
        )

        assert result.success is True
        assert result.status == "completed"
        assert result.workflow_id == "z_image_turbo"
        assert result.job_id == "test-123"
        assert len(result.outputs) == 1
        assert result.outputs[0]["filename"] == "image.png"
        assert result.outputs[0]["size_bytes"] > 0
        assert result.metadata.get("prompt_id") == "test-123"

    @patch("comfyui.services.executor.ComfyApiWrapper")
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_sets_positive_prompt_on_workflow(self, MockWF, MockAPI, skill_root):
        mock_wf_instance = MagicMock()
        mock_wf_instance.get_node_id.return_value = "9"
        MockWF.return_value = mock_wf_instance
        MockAPI.return_value = _make_mock_api(
            prompt_id="p1",
            history={"p1": {"outputs": {"9": {"images": []}}}},
        )

        execute_workflow(
            config=Z_IMAGE_TURBO,
            prompt="test prompt",
            skill_root=skill_root,
            results_dir=skill_root / "results" / "test",
        )

        mock_wf_instance.set_node_param.assert_any_call(
            "CLIP Text Encode (Positive Prompt)", "text", "test prompt"
        )


class TestExecuteWorkflowFailure:
    @patch("comfyui.services.executor.ComfyApiWrapper")
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_handles_execution_exception(self, MockWF, MockAPI, skill_root):
        MockWF.return_value = MagicMock()
        MockAPI.return_value = _make_mock_api(
            queue_side_effect=RuntimeError("Connection refused"),
        )

        result = execute_workflow(config=Z_IMAGE_TURBO, prompt="test prompt", skill_root=skill_root)
        assert result.success is False
        assert result.error["code"] == "EXECUTION_FAILED"
        assert "Connection refused" in result.error["message"]

    @patch("comfyui.services.executor.ComfyApiWrapper")
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_handles_no_images_produced(self, MockWF, MockAPI, skill_root):
        mock_wf_instance = MagicMock()
        mock_wf_instance.get_node_id.return_value = "9"
        MockWF.return_value = mock_wf_instance
        MockAPI.return_value = _make_mock_api(
            prompt_id="p1",
            history={"p1": {"outputs": {"9": {"images": []}}}},
        )

        result = execute_workflow(config=Z_IMAGE_TURBO, prompt="test prompt", skill_root=skill_root)
        assert result.success is False
        assert result.error["code"] == "NO_OUTPUT"


class TestExecuteWorkflowSeed:
    @patch("comfyui.services.executor.ComfyApiWrapper")
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_explicit_seed_set_on_sampler(self, MockWF, MockAPI, skill_root):
        mock_wf_instance = MagicMock()
        mock_wf_instance.get_node_id.return_value = "9"
        MockWF.return_value = mock_wf_instance
        MockAPI.return_value = _make_mock_api()

        result = execute_workflow(
            config=Z_IMAGE_TURBO,
            prompt="test prompt",
            skill_root=skill_root,
            results_dir=skill_root / "results" / "test",
            seed=42,
        )

        assert result.success is True
        assert result.metadata["seed"] == 42
        mock_wf_instance.set_node_param.assert_any_call("KSampler", "seed", 42)

    @patch("comfyui.services.executor.ComfyApiWrapper")
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_random_seed_when_not_specified(self, MockWF, MockAPI, skill_root):
        mock_wf_instance = MagicMock()
        mock_wf_instance.get_node_id.return_value = "9"
        MockWF.return_value = mock_wf_instance
        MockAPI.return_value = _make_mock_api()

        result = execute_workflow(
            config=Z_IMAGE_TURBO,
            prompt="test prompt",
            skill_root=skill_root,
            results_dir=skill_root / "results" / "test",
        )

        assert result.success is True
        assert isinstance(result.metadata["seed"], int)
        # Seed should be a reasonable positive int
        assert result.metadata["seed"] >= 0


class TestExecuteWorkflowImageUpload:
    def _make_img_config(self, tmp_path):
        return WorkflowConfig(
            workflow_id="test_img",
            workflow_file="test.json",
            output_node_title="Save Image",
            node_mapping={
                "input_image": {
                    "node_title": "Load Image",
                    "param": "image",
                    "value_type": "image",
                    "input_strategy": "upload",
                    "required": True,
                },
                "prompt": {"node_title": "Prompt Node", "param": "text", "required": True},
                "seed": {"node_title": "KSampler", "param": "seed", "value_type": "integer", "auto_random": True},
            },
            size_strategy="workflow_managed",
        )

    @patch("comfyui.services.executor.ComfyApiWrapper")
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_upload_and_bind_image(self, MockWF, MockAPI, tmp_path):
        mock_wf_instance = MagicMock()
        mock_wf_instance.get_node_id.return_value = "9"
        MockWF.return_value = mock_wf_instance
        mock_api = _make_mock_api()
        mock_api.upload_image.return_value = {"name": "photo.png", "subfolder": "default_upload_folder", "type": "input"}
        MockAPI.return_value = mock_api

        # Create a dummy image file
        img_path = tmp_path / "photo.png"
        img_path.write_bytes(b"fake image data")
        # Create a dummy workflow JSON
        wf_path = tmp_path / "assets" / "workflows" / "test.json"
        wf_path.parent.mkdir(parents=True, exist_ok=True)
        wf_path.write_text('{"1": {"class_type": "Test"}}')

        config = self._make_img_config(tmp_path)
        result = execute_workflow(
            config=config,
            prompt="change hair to pink",
            skill_root=tmp_path,
            input_images={"input_image": img_path},
        )

        assert result.success is True
        mock_api.upload_image.assert_called_once_with(str(img_path))
        mock_wf_instance.set_node_param.assert_any_call(
            "Load Image", "image", "default_upload_folder/photo.png"
        )

    def test_missing_required_image_returns_error(self, tmp_path):
        config = self._make_img_config(tmp_path)
        wf_path = tmp_path / "assets" / "workflows" / "test.json"
        wf_path.parent.mkdir(parents=True, exist_ok=True)
        wf_path.write_text('{"1": {"class_type": "Test"}}')

        result = execute_workflow(
            config=config,
            prompt="change hair to pink",
            skill_root=tmp_path,
            input_images={},
        )
        assert result.success is False
        assert result.error["code"] == "NO_INPUT_IMAGE"

    def test_image_file_not_found(self, tmp_path):
        config = self._make_img_config(tmp_path)
        wf_path = tmp_path / "assets" / "workflows" / "test.json"
        wf_path.parent.mkdir(parents=True, exist_ok=True)
        wf_path.write_text('{"1": {"class_type": "Test"}}')

        result = execute_workflow(
            config=config,
            prompt="change hair to pink",
            skill_root=tmp_path,
            input_images={"input_image": tmp_path / "nonexistent.png"},
        )
        assert result.success is False
        assert result.error["code"] == "INPUT_IMAGE_NOT_FOUND"

    @patch("comfyui.services.executor.ComfyApiWrapper")
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_upload_failure_returns_error(self, MockWF, MockAPI, tmp_path):
        MockWF.return_value = MagicMock()
        mock_api = _make_mock_api()
        mock_api.upload_image.side_effect = RuntimeError("Upload failed")
        MockAPI.return_value = mock_api

        img_path = tmp_path / "photo.png"
        img_path.write_bytes(b"fake image data")
        wf_path = tmp_path / "assets" / "workflows" / "test.json"
        wf_path.parent.mkdir(parents=True, exist_ok=True)
        wf_path.write_text('{"1": {"class_type": "Test"}}')

        config = self._make_img_config(tmp_path)
        result = execute_workflow(
            config=config,
            prompt="change hair to pink",
            skill_root=tmp_path,
            input_images={"input_image": img_path},
        )
        assert result.success is False
        assert result.error["code"] == "IMAGE_UPLOAD_FAILED"

    @patch("comfyui.services.executor.ComfyApiWrapper")
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_upload_with_empty_subfolder(self, MockWF, MockAPI, tmp_path):
        mock_wf_instance = MagicMock()
        mock_wf_instance.get_node_id.return_value = "9"
        MockWF.return_value = mock_wf_instance
        mock_api = _make_mock_api()
        mock_api.upload_image.return_value = {"name": "photo.png", "subfolder": "", "type": "input"}
        MockAPI.return_value = mock_api

        img_path = tmp_path / "photo.png"
        img_path.write_bytes(b"fake image data")
        wf_path = tmp_path / "assets" / "workflows" / "test.json"
        wf_path.parent.mkdir(parents=True, exist_ok=True)
        wf_path.write_text('{"1": {"class_type": "Test"}}')

        config = self._make_img_config(tmp_path)
        result = execute_workflow(
            config=config,
            prompt="change hair to pink",
            skill_root=tmp_path,
            input_images={"input_image": img_path},
        )

        assert result.success is True
        mock_wf_instance.set_node_param.assert_any_call(
            "Load Image", "image", "photo.png"
        )
