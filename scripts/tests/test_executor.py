"""Tests for the generic workflow executor."""
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from comfyui.models.result import GenerationResult
from comfyui.services.executor import execute_workflow, node_output_media_list
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
    def test_default_results_dir_uses_date_and_prompt_id(self, MockWF, MockAPI, skill_root):
        mock_wf_instance = MagicMock()
        mock_wf_instance.get_node_id.return_value = "9"
        MockWF.return_value = mock_wf_instance
        MockAPI.return_value = _make_mock_api(prompt_id="test-123")

        result = execute_workflow(
            config=Z_IMAGE_TURBO,
            prompt="a cute cat",
            skill_root=skill_root,
        )

        assert result.success is True
        out_path = Path(result.outputs[0]["path"])
        rel = out_path.relative_to(skill_root)
        assert rel.parts[0] == "results"
        assert re.fullmatch(r"\d{8}", rel.parts[1])
        assert re.match(r"\d{6}_test-123", rel.parts[2])

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


class TestProgressAndErrors:
    @patch("comfyui.services.executor._queue_prompt_and_wait_with_progress", new_callable=AsyncMock)
    @patch("comfyui.services.executor.ComfyApiWrapper")
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_progress_callback_invoked(self, MockWF, MockAPI, mock_wait, skill_root):
        async def _side_effect(api, wf, on_progress):
            on_progress({"phase": "queued", "prompt_id": "p1"})
            return "test-123"

        mock_wait.side_effect = _side_effect
        mock_wf_instance = MagicMock()
        mock_wf_instance.get_node_id.return_value = "9"
        MockWF.return_value = mock_wf_instance
        MockAPI.return_value = _make_mock_api(prompt_id="test-123")

        events: list[dict] = []

        def cb(ev: dict) -> None:
            events.append(ev)

        result = execute_workflow(
            config=Z_IMAGE_TURBO,
            prompt="a cute cat",
            skill_root=skill_root,
            results_dir=skill_root / "results" / "test",
            progress_callback=cb,
        )
        assert result.success is True
        assert any(e.get("phase") == "queued" for e in events)

    @patch("comfyui.services.executor.ComfyApiWrapper", side_effect=ConnectionError("Connection refused"))
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_api_init_connection_error_includes_hint(self, MockWF, skill_root):
        result = execute_workflow(
            config=Z_IMAGE_TURBO,
            prompt="a test",
            skill_root=skill_root,
        )
        assert result.success is False
        assert result.error["code"] == "SERVER_UNAVAILABLE"
        assert "提示" in result.error["message"] or "127.0.0.1" in result.error["message"] or "运行" in result.error["message"]


class TestNodeOutputMediaList:
    def test_video_empty_when_no_known_keys(self):
        assert node_output_media_list({}, "video") == []

    def test_video_prefers_images_then_gifs(self):
        gif_only = {"gifs": [{"filename": "a.mp4"}]}
        assert node_output_media_list(gif_only, "video")[0]["filename"] == "a.mp4"

        both = {
            "images": [{"filename": "thumb.png"}],
            "gifs": [{"filename": "clip.mp4"}],
        }
        assert node_output_media_list(both, "video")[0]["filename"] == "thumb.png"

    def test_audio_uses_audio_key(self):
        out = {"audio": [{"filename": "x.mp3"}]}
        assert node_output_media_list(out, "audio")[0]["filename"] == "x.mp3"


class TestExecuteWorkflowDimensions:
    """Width/height application: node_mapping + size_strategy (LTX-style EmptyImage)."""

    def _write_minimal_workflow(self, skill_root: Path, name: str = "dim_test.json") -> None:
        wf_path = skill_root / "assets" / "workflows" / name
        wf_path.parent.mkdir(parents=True, exist_ok=True)
        wf_path.write_text('{"1": {"class_type": "Stub"}}')

    def _config_empty_image(self, wf_file: str = "dim_test.json") -> WorkflowConfig:
        return WorkflowConfig(
            workflow_id="dim_test",
            workflow_file=wf_file,
            output_node_title="Save Image",
            node_mapping={
                "prompt": {
                    "node_title": "CLIP Text Encode (Positive Prompt)",
                    "param": "text",
                    "value_type": "string",
                    "required": True,
                },
                "width": {
                    "node_title": "EmptyImage",
                    "param": "width",
                    "value_type": "integer",
                    "default": 768,
                },
                "height": {
                    "node_title": "EmptyImage",
                    "param": "height",
                    "value_type": "integer",
                    "default": 512,
                },
            },
        )

    @patch("comfyui.services.executor.ComfyApiWrapper")
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_applies_default_width_height_to_empty_image(self, MockWF, MockAPI, tmp_path):
        mock_wf = MagicMock()
        mock_wf.get_node_id.return_value = "9"
        MockWF.return_value = mock_wf
        MockAPI.return_value = _make_mock_api()

        self._write_minimal_workflow(tmp_path)
        cfg = self._config_empty_image()
        result = execute_workflow(
            config=cfg,
            prompt="motion test",
            skill_root=tmp_path,
            results_dir=tmp_path / "out",
        )
        assert result.success is True
        mock_wf.set_node_param.assert_any_call("EmptyImage", "width", 768)
        mock_wf.set_node_param.assert_any_call("EmptyImage", "height", 512)
        assert result.metadata["width"] == 768
        assert result.metadata["height"] == 512

    @patch("comfyui.services.executor.ComfyApiWrapper")
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_applies_explicit_width_height_over_defaults(self, MockWF, MockAPI, tmp_path):
        mock_wf = MagicMock()
        mock_wf.get_node_id.return_value = "9"
        MockWF.return_value = mock_wf
        MockAPI.return_value = _make_mock_api()

        self._write_minimal_workflow(tmp_path)
        cfg = self._config_empty_image()
        result = execute_workflow(
            config=cfg,
            prompt="motion test",
            skill_root=tmp_path,
            results_dir=tmp_path / "out",
            width=1920,
            height=1088,
        )
        assert result.success is True
        mock_wf.set_node_param.assert_any_call("EmptyImage", "width", 1920)
        mock_wf.set_node_param.assert_any_call("EmptyImage", "height", 1088)

    @patch("comfyui.services.executor.ComfyApiWrapper")
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_workflow_managed_skips_dimension_params(self, MockWF, MockAPI, tmp_path):
        mock_wf = MagicMock()
        mock_wf.get_node_id.return_value = "9"
        MockWF.return_value = mock_wf
        MockAPI.return_value = _make_mock_api()

        self._write_minimal_workflow(tmp_path, "managed.json")
        cfg = WorkflowConfig(
            workflow_id="managed_dim",
            workflow_file="managed.json",
            output_node_title="Save Image",
            size_strategy="workflow_managed",
            node_mapping={
                "prompt": {
                    "node_title": "CLIP Text Encode (Positive Prompt)",
                    "param": "text",
                    "value_type": "string",
                    "required": True,
                },
                "width": {
                    "node_title": "EmptyImage",
                    "param": "width",
                    "value_type": "integer",
                    "default": 999,
                },
                "height": {
                    "node_title": "EmptyImage",
                    "param": "height",
                    "value_type": "integer",
                    "default": 888,
                },
            },
        )
        result = execute_workflow(
            config=cfg,
            prompt="test",
            skill_root=tmp_path,
            results_dir=tmp_path / "out",
            width=1920,
            height=1088,
        )
        assert result.success is True
        for call in mock_wf.set_node_param.call_args_list:
            args, _kwargs = call
            assert args[0] != "EmptyImage" or args[1] not in ("width", "height")
        assert "width" not in result.metadata
        assert "height" not in result.metadata

    @patch("comfyui.services.executor.ComfyApiWrapper")
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_video_output_reads_gifs_key(self, MockWF, MockAPI, tmp_path):
        mock_wf = MagicMock()
        mock_wf.get_node_id.return_value = "186"
        MockWF.return_value = mock_wf
        mock_api = _make_mock_api(
            prompt_id="v1",
            history={
                "v1": {
                    "outputs": {
                        "186": {
                            "gifs": [
                                {
                                    "filename": "out.mp4",
                                    "subfolder": "ltx-2.3",
                                    "type": "output",
                                }
                            ]
                        }
                    }
                }
            },
            image_data=b"fake mp4 bytes",
        )
        MockAPI.return_value = mock_api

        self._write_minimal_workflow(tmp_path, "video_out.json")
        cfg = WorkflowConfig(
            workflow_id="video_out",
            workflow_file="video_out.json",
            output_node_title="Video Combine (Primary MP4)",
            output_kind="video",
            node_mapping={
                "prompt": {
                    "node_title": "P",
                    "param": "text",
                    "value_type": "string",
                    "required": True,
                },
            },
        )
        result = execute_workflow(
            config=cfg,
            prompt="a video",
            skill_root=tmp_path,
            results_dir=tmp_path / "out",
        )
        assert result.success is True
        assert result.outputs[0]["filename"] == "out.mp4"
