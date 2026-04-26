"""Tests for the CLI entry point (run.py)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

RUN_PY = Path(__file__).resolve().parent.parent / "run.py"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUN_PY), *args],
        capture_output=True,
        text=True,
        cwd=str(RUN_PY.parent.parent.parent),  # skill root as cwd
    )


class TestCLICheckMode:
    def test_check_flag_returns_json(self):
        result = _run_cli("--check")
        data = json.loads(result.stdout)
        assert "available" in data
        assert "url" in data

    def test_check_with_custom_server(self):
        result = _run_cli("--check", "--server", "http://127.0.0.1:59999")
        data = json.loads(result.stdout)
        assert data["available"] is False
        assert result.returncode == 1


class TestCLIPrompt:
    def test_missing_prompt_shows_error(self):
        result = _run_cli()
        assert result.returncode != 0
        data = json.loads(result.stdout)
        assert data["success"] is False
        assert data["error"]["code"] == "EMPTY_PROMPT"

    def test_prompt_via_flag(self):
        """--prompt flag should work as alternative to positional."""
        result = _run_cli("--server", "http://127.0.0.1:59999", "--prompt", "test")
        # Will fail because server is down, but should parse args correctly
        data = json.loads(result.stdout)
        assert data["success"] is False
        assert "server" in data["status"] or "unavailable" in data["status"].lower()


class TestCLIWorkflowFlag:
    def test_workflow_flag_accepted(self):
        """--workflow z_image_turbo should be accepted (even if server is down)."""
        result = _run_cli(
            "--server", "http://127.0.0.1:59999",
            "--workflow", "z_image_turbo",
            "--prompt", "test",
        )
        # Server is down so it fails, but args should parse
        data = json.loads(result.stdout)
        assert data["workflow_id"] == "z_image_turbo"

    def test_workflow_flag_invalid(self):
        """--workflow with unknown value should return structured error."""
        result = _run_cli(
            "--server", "http://127.0.0.1:59999",
            "--workflow", "nonexistent",
            "--prompt", "test",
        )
        assert result.returncode != 0
        data = json.loads(result.stdout)
        assert data["error"]["code"] == "WORKFLOW_NOT_REGISTERED"
        assert data["workflow_id"] == "nonexistent"

    def test_default_workflow_is_z_image_turbo(self):
        """Without --workflow, should default to z_image_turbo."""
        result = _run_cli(
            "--server", "http://127.0.0.1:59999",
            "--prompt", "test",
        )
        data = json.loads(result.stdout)
        assert data["workflow_id"] == "z_image_turbo"


class TestCLICount:
    def test_count_flag_with_server_down(self):
        """--count 2 should parse correctly even when server is down."""
        result = _run_cli(
            "--server", "http://127.0.0.1:59999",
            "--count", "2",
            "--prompt", "test",
        )
        data = json.loads(result.stdout)
        assert data["success"] is False
        assert "unavailable" in data["status"].lower()

    def test_count_default_is_one(self):
        """Without --count, defaults to 1 (single execution)."""
        result = _run_cli(
            "--server", "http://127.0.0.1:59999",
            "--prompt", "test",
        )
        data = json.loads(result.stdout)
        # Single result, not a list
        assert isinstance(data, dict)
        assert "workflow_id" in data


class TestCLISaveServer:
    def test_save_server_creates_config(self, tmp_path):
        """--save-server writes URL to config.local.json."""
        config_file = tmp_path / "config.local.json"
        result = _run_cli("--save-server", "http://192.168.1.100:8188")
        data = json.loads(result.stdout)
        assert data["saved"] is True
        assert data["comfyui_url"] == "http://192.168.1.100:8188"
        assert result.returncode == 0


class TestCLIImage:
    def test_image_file_not_found(self):
        result = _run_cli(
            "--server", "http://127.0.0.1:59999",
            "--workflow", "klein_edit",
            "--image", "input_image=nonexistent.png",
            "--prompt", "test",
        )
        assert result.returncode != 0
        data = json.loads(result.stdout)
        assert data["error"]["code"] == "INPUT_IMAGE_NOT_FOUND"

    def test_image_bare_path_single_role(self):
        """Bare path should auto-match when workflow has one image role."""
        # Create a dummy file so it doesn't fail on existence check
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake")
            tmp_img = f.name
        try:
            result = _run_cli(
                "--server", "http://127.0.0.1:59999",
                "--workflow", "klein_edit",
                "--image", tmp_img,
                "--prompt", "test",
            )
            data = json.loads(result.stdout)
            # Will fail on server, but should get past image parsing
            assert data["error"]["code"] != "INPUT_IMAGE_NOT_FOUND"
        finally:
            Path(tmp_img).unlink(missing_ok=True)
