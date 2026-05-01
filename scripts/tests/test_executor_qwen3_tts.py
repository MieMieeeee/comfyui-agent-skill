"""Executor tests for qwen3_tts (audio output, speech_text + instruct)."""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from comfyui.services.executor import execute_workflow
from comfyui.services.workflow_config import WORKFLOW_REGISTRY


@pytest.fixture
def qwen_config():
    return WORKFLOW_REGISTRY["qwen3_tts"]


def _mock_api_audio(prompt_id="tts-1", filename="out.mp3"):
    mock_api = MagicMock()
    mock_api.queue_prompt_and_wait = AsyncMock(return_value=prompt_id)
    mock_api.get_history.return_value = {
        prompt_id: {
            "outputs": {
                "47": {
                    "audio": [{"filename": filename, "subfolder": "audio", "type": "output"}]
                }
            }
        }
    }
    mock_api.get_image.return_value = b"id3fake"
    return mock_api


class TestQwen3TTSValidation:
    def test_requires_speech_text(self, skill_root, qwen_config):
        result = execute_workflow(
            qwen_config,
            "",
            skill_root,
            text_inputs={"instruct": "some style"},
        )
        assert result.success is False
        assert result.error["code"] == "EMPTY_SPEECH_TEXT"

    def test_requires_instruct(self, skill_root, qwen_config):
        result = execute_workflow(
            qwen_config,
            "",
            skill_root,
            text_inputs={"speech_text": "hello"},
        )
        assert result.success is False
        assert result.error["code"] == "EMPTY_INSTRUCT"


class TestQwen3TTSSuccess:
    @patch("comfyui.services.executor.ComfyApiWrapper")
    @patch("comfyui.services.executor.ComfyWorkflowWrapper")
    def test_saves_mp3_and_returns_outputs(self, MockWF, MockAPI, skill_root, qwen_config, tmp_path):
        mock_wf_instance = MagicMock()
        mock_wf_instance.get_node_id.return_value = "47"
        MockWF.return_value = mock_wf_instance
        MockAPI.return_value = _mock_api_audio()

        out = tmp_path / "tts_out"
        result = execute_workflow(
            qwen_config,
            "",
            skill_root,
            results_dir=out,
            text_inputs={
                "speech_text": "你好",
                "instruct": "温柔女声",
            },
        )

        assert result.success is True
        assert len(result.outputs) == 1
        assert result.outputs[0]["filename"] == "out.mp3"
        assert Path(result.outputs[0]["path"]).exists()
        assert result.metadata.get("speech_text") == "你好"
        assert result.metadata.get("instruct") == "温柔女声"
