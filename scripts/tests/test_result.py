"""Tests for result model and metadata preservation."""
import pytest

from comfyui.models.result import GenerationResult


class TestGenerationResult:
    def test_to_dict_roundtrip(self):
        result = GenerationResult(
            success=True,
            workflow_id="test",
            status="completed",
            outputs=[{"path": "/tmp/img.png", "filename": "img.png", "size_bytes": 100}],
            job_id="prompt-abc-123",
            metadata={"prompt": "cat", "prompt_id": "prompt-abc-123", "width": 832, "height": 1280},
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["job_id"] == "prompt-abc-123"
        assert d["metadata"]["prompt_id"] == "prompt-abc-123"
        assert len(d["outputs"]) == 1

    def test_result_preserves_comfyui_history(self):
        comfyui_raw = {"outputs": {"9": {"images": [{"filename": "img.png"}]}}}
        result = GenerationResult(
            success=True,
            workflow_id="z_image_turbo",
            status="completed",
            metadata={"comfyui_history": comfyui_raw},
        )
        assert result.metadata["comfyui_history"]["outputs"]["9"]["images"][0]["filename"] == "img.png"


class TestStructuredError:
    """Test that error is structured as {code, message} dict."""

    def test_error_is_dict_with_code_and_message(self):
        result = GenerationResult(
            success=False,
            workflow_id="test",
            status="failed",
            error={"code": "EMPTY_PROMPT", "message": "Prompt is empty."},
        )
        d = result.to_dict()
        assert isinstance(d["error"], dict)
        assert d["error"]["code"] == "EMPTY_PROMPT"
        assert d["error"]["message"] == "Prompt is empty."

    def test_error_defaults_to_none(self):
        result = GenerationResult(success=True, workflow_id="test", status="completed")
        assert result.error is None
        assert result.to_dict()["error"] is None

    def test_server_unavailable_error(self):
        result = GenerationResult(
            success=False,
            workflow_id="test",
            status="server_unavailable",
            error={"code": "SERVER_UNAVAILABLE", "message": "ComfyUI not reachable"},
        )
        assert result.error["code"] == "SERVER_UNAVAILABLE"

    def test_execution_failed_error(self):
        result = GenerationResult(
            success=False,
            workflow_id="test",
            status="failed",
            error={"code": "EXECUTION_FAILED", "message": "Connection refused"},
        )
        assert result.error["code"] == "EXECUTION_FAILED"
