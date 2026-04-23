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
        # argparse prints to stderr
        assert "prompt" in result.stderr.lower() or "required" in result.stderr.lower()

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
        """--workflow with unknown value should fail."""
        result = _run_cli(
            "--server", "http://127.0.0.1:59999",
            "--workflow", "nonexistent",
            "--prompt", "test",
        )
        assert result.returncode != 0

    def test_default_workflow_is_z_image_turbo(self):
        """Without --workflow, should default to z_image_turbo."""
        result = _run_cli(
            "--server", "http://127.0.0.1:59999",
            "--prompt", "test",
        )
        data = json.loads(result.stdout)
        assert data["workflow_id"] == "z_image_turbo"
