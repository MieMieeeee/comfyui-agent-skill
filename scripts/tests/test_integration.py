"""Integration tests against a live ComfyUI server.

These tests require a running ComfyUI server at 127.0.0.1:8188
with the z_image_turbo model loaded.

Run with: python -m pytest scripts/tests/test_integration.py -v
Skip with: python -m pytest scripts/tests/ -v --ignore=scripts/tests/test_integration.py
"""
import json
from pathlib import Path

import pytest

from comfyui.config import check_server
from comfyui.services.executor import execute_workflow
from comfyui.services.workflow_config import Z_IMAGE_TURBO, WORKFLOW_REGISTRY

SERVER_URL = "http://127.0.0.1:8188"
SKILL_ROOT = Path(__file__).resolve().parent.parent.parent


def _server_available() -> bool:
    return check_server(SERVER_URL)["available"]


requires_server = pytest.mark.skipif(
    not _server_available(),
    reason="ComfyUI server not available at 127.0.0.1:8188",
)


@requires_server
class TestCheckServerLive:
    def test_system_stats_returns_valid_data(self):
        result = check_server(SERVER_URL)
        assert result["available"] is True
        assert "stats" in result
        stats = result["stats"]
        assert "system" in stats
        assert "ram_total" in stats["system"]
        assert stats["system"]["ram_total"] > 0

    def test_comfyui_version_present(self):
        result = check_server(SERVER_URL)
        assert result["stats"]["system"]["comfyui_version"] is not None

    def test_gpu_info_present(self):
        result = check_server(SERVER_URL)
        devices = result["stats"].get("devices", [])
        assert len(devices) > 0
        # At least one GPU entry should have a name
        assert any(d.get("name") for d in devices)


@requires_server
class TestExecuteZImageTurboLive:
    def test_generates_image_from_prompt(self, tmp_path):
        result = execute_workflow(
            config=Z_IMAGE_TURBO,
            prompt="a simple red circle on white background, minimal",
            skill_root=SKILL_ROOT,
            server_url=SERVER_URL,
            results_dir=tmp_path / "results",
        )

        assert result.success is True
        assert result.status == "completed"
        assert result.workflow_id == "z_image_turbo"

        # prompt_id is preserved
        assert result.job_id is not None
        assert result.metadata.get("prompt_id") == result.job_id

        # At least one image produced
        assert len(result.outputs) >= 1

        # Output file actually exists on disk
        for out in result.outputs:
            assert Path(out["path"]).exists()
            assert out["size_bytes"] > 0
            assert out["size_bytes"] == Path(out["path"]).stat().st_size

    def test_image_is_valid_png(self, tmp_path):
        result = execute_workflow(
            config=Z_IMAGE_TURBO,
            prompt="a blue square, simple test image",
            skill_root=SKILL_ROOT,
            server_url=SERVER_URL,
            results_dir=tmp_path / "results",
        )

        assert result.success is True
        for out in result.outputs:
            data = Path(out["path"]).read_bytes()
            # PNG magic bytes
            assert data[:4] == b"\x89PNG"

    def test_empty_prompt_fails_gracefully(self, tmp_path):
        result = execute_workflow(
            config=Z_IMAGE_TURBO,
            prompt="",
            skill_root=SKILL_ROOT,
            server_url=SERVER_URL,
            results_dir=tmp_path / "results",
        )

        assert result.success is False
        assert result.status == "failed"
        assert result.error["code"] == "EMPTY_PROMPT"


@requires_server
class TestWorkflowRegistryLive:
    def test_registry_contains_z_image_turbo(self):
        assert "z_image_turbo" in WORKFLOW_REGISTRY
        cfg = WORKFLOW_REGISTRY["z_image_turbo"]
        assert cfg.workflow_file == "z_image_turbo.json"
        resolved = cfg.resolve_workflow_path(SKILL_ROOT)
        assert resolved.exists()

    def test_all_registered_workflows_have_files(self):
        for wid, cfg in WORKFLOW_REGISTRY.items():
            resolved = cfg.resolve_workflow_path(SKILL_ROOT)
            assert resolved.exists(), f"Workflow {wid}: file not found at {resolved}"


@requires_server
class TestCLIIntegration:
    def test_cli_check_mode(self):
        import subprocess
        import sys

        run_py = Path(__file__).resolve().parent.parent / "run.py"
        proc = subprocess.run(
            [sys.executable, str(run_py), "--check", "--server", SERVER_URL],
            capture_output=True,
            text=True,
            cwd=str(SKILL_ROOT),
        )
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert data["available"] is True

    def test_cli_generate_image(self, tmp_path):
        import subprocess
        import sys

        run_py = Path(__file__).resolve().parent.parent / "run.py"
        out_dir = tmp_path / "cli_results"
        proc = subprocess.run(
            [
                sys.executable, str(run_py),
                "--server", SERVER_URL,
                "--output", str(out_dir),
                "--prompt", "a green triangle on white background",
            ],
            capture_output=True,
            text=True,
            cwd=str(SKILL_ROOT),
            timeout=120,
        )

        data = json.loads(proc.stdout)
        assert data["success"] is True
        assert data["workflow_id"] == "z_image_turbo"
        assert len(data["outputs"]) >= 1
        assert Path(data["outputs"][0]["path"]).exists()
