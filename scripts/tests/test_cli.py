"""Tests for the CLI entry point (run.py) and `python -m comfyui`。"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from comfyui.cli import resolve_output_directory

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
RUN_PY = Path(__file__).resolve().parent.parent / "run.py"
SCRIPTS_DIR = RUN_PY.parent


def _run_cli(*args: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, **(extra_env or {})}
    return subprocess.run(
        [sys.executable, str(RUN_PY), *args],
        capture_output=True,
        text=True,
        cwd=str(SKILL_ROOT),
        env=env,
    )


def _run_module(*args: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(SCRIPTS_DIR), **(extra_env or {})}
    return subprocess.run(
        [sys.executable, "-m", "comfyui", *args],
        capture_output=True,
        text=True,
        cwd=str(SKILL_ROOT),
        env=env,
    )


class TestResolveOutputDirectory:
    def test_none_uses_fallback(self, tmp_path):
        fb = tmp_path / "default" / "out"
        assert resolve_output_directory(None, fallback=fb) == fb
        assert resolve_output_directory("", fallback=fb) == fb
        assert resolve_output_directory("   ", fallback=fb) == fb

    def test_existing_directory(self, tmp_path):
        d = tmp_path / "mydir"
        d.mkdir()
        fb = tmp_path / "fb"
        assert resolve_output_directory(str(d), fallback=fb) == d.resolve()

    def test_png_path_uses_parent(self, tmp_path):
        fb = tmp_path / "fb"
        target = tmp_path / "nested" / "cat.png"
        assert resolve_output_directory(str(target), fallback=fb) == (tmp_path / "nested").resolve()

    def test_bare_png_uses_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        fb = tmp_path / "fb"
        assert resolve_output_directory("cat.png", fallback=fb) == tmp_path.resolve()

    def test_plain_dir_string_even_if_missing(self, tmp_path):
        fb = tmp_path / "fb"
        out = tmp_path / "new_results" / "batch1"
        assert resolve_output_directory(str(out), fallback=fb) == out.resolve()


class TestComfyuiModule:
    def test_module_check_matches_run_py(self):
        a = _run_cli("--check", "--server", "http://127.0.0.1:59999")
        b = _run_module("check", "--server", "http://127.0.0.1:59999")
        assert json.loads(a.stdout) == json.loads(b.stdout)
        assert a.returncode == b.returncode

    def test_module_unknown_subcommand_exits_2(self):
        r = _run_module("nope")
        assert r.returncode == 2
        assert "unknown" in r.stderr.lower() or "未知" in r.stderr


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


class TestCLIQwen3TTS:
    def test_tts_requires_speech_text_and_instruct(self):
        result = _run_cli(
            "--server", "http://127.0.0.1:59999",
            "--workflow", "qwen3_tts",
            "--instruct", "some voice style",
        )
        assert result.returncode != 0
        data = json.loads(result.stdout)
        assert data["error"]["code"] == "EMPTY_SPEECH_TEXT"

    def test_tts_rejects_positional_prompt_with_server_down(self):
        result = _run_cli(
            "--server", "http://127.0.0.1:59999",
            "--workflow", "qwen3_tts",
            "hello world",
        )
        data = json.loads(result.stdout)
        assert data["error"]["code"] == "INVALID_ARGS"


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
        """--save-server writes URL to the file given by COMFYUI_CONFIG_FILE."""
        config_file = tmp_path / "config.local.json"
        result = _run_cli(
            "--save-server",
            "http://192.168.1.100:8188",
            extra_env={"COMFYUI_CONFIG_FILE": str(config_file)},
        )
        data = json.loads(result.stdout)
        assert data["saved"] is True
        assert data["comfyui_url"] == "http://192.168.1.100:8188"
        assert Path(data["config_file"]) == config_file.resolve()
        assert result.returncode == 0
        on_disk = json.loads(config_file.read_text(encoding="utf-8"))
        assert on_disk["comfyui_url"] == "http://192.168.1.100:8188"


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


class TestCLISubmit:
    def test_submit_flag_requires_workflow(self):
        """--submit without --workflow should fail."""
        result = _run_cli("--submit", "--prompt", "test")
        # Should exit with error
        assert result.returncode != 0

    def test_submit_missing_workflow_shows_error(self):
        """--submit with unknown workflow returns structured error."""
        result = _run_module(
            "--server", "http://127.0.0.1:59999",
            "--submit",
            "--workflow", "nonexistent_workflow",
            "--prompt", "test",
        )
        data = json.loads(result.stdout)
        assert data["error"]["code"] == "WORKFLOW_NOT_REGISTERED"

    def test_submit_empty_prompt_shows_error(self):
        """--submit with empty prompt returns structured error."""
        result = _run_module(
            "--server", "http://127.0.0.1:59999",
            "--submit",
            "--workflow", "z_image_turbo",
            "--prompt", "",
        )
        data = json.loads(result.stdout)
        assert data["submitted"] is False
        assert data["error"]["code"] == "EMPTY_PROMPT"

    def test_submit_without_server_flag(self):
        """--submit without --server uses config/default."""
        result = _run_module(
            "--submit",
            "--workflow", "z_image_turbo",
            "--prompt", "a cute cat",
        )
        # Will fail on server but should parse args
        data = json.loads(result.stdout)
        assert "submitted" in data or "error" in data


class TestCLIPoll:
    def test_poll_requires_job_id(self):
        """--poll without job_id should show error."""
        result = _run_module("--poll")
        assert result.returncode != 0

    def test_poll_job_not_found(self, tmp_path):
        """--poll for unknown job_id returns unknown status."""
        db = tmp_path / "jobs.db"
        from comfyui.services.job_store import JobStore
        JobStore(db)  # create empty db

        result = _run_module(
            "--poll", "nonexistent-job",
            extra_env={"COMFYUI_JOB_STORE": str(db)},
        )
        data = json.loads(result.stdout)
        assert data["job_id"] == "nonexistent-job"
        assert data["status"] == "unknown"

    def test_poll_returns_current_status(self, tmp_path):
        """--poll returns current job status from store."""
        db = tmp_path / "jobs.db"
        from comfyui.services.job_store import JobStore
        store = JobStore(db)
        store.save_job(
            job_id="abc123",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="submitted",
        )

        result = _run_module(
            "--poll", "abc123",
            extra_env={"COMFYUI_JOB_STORE": str(db)},
        )
        data = json.loads(result.stdout)
        assert data["job_id"] == "abc123"
        assert data["status"] == "submitted"


class TestCLIPollAll:
    def test_poll_all_empty_store(self, tmp_path):
        """--poll-all with empty store returns empty list."""
        db = tmp_path / "jobs.db"
        from comfyui.services.job_store import JobStore
        JobStore(db)

        result = _run_module(
            "--poll-all",
            extra_env={"COMFYUI_JOB_STORE": str(db)},
        )
        data = json.loads(result.stdout)
        assert data["jobs"] == []

    def test_poll_all_returns_pending_jobs(self, tmp_path):
        """--poll-all returns all pending jobs."""
        db = tmp_path / "jobs.db"
        from comfyui.services.job_store import JobStore
        store = JobStore(db)
        store.save_job(
            job_id="job-1",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="submitted",
        )
        store.save_job(
            job_id="job-2",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="completed",
        )

        result = _run_module(
            "--poll-all",
            extra_env={"COMFYUI_JOB_STORE": str(db)},
        )
        data = json.loads(result.stdout)
        # poll_all returns submitted+executing only; completed jobs are excluded
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["job_id"] == "job-1"


class TestCLIAsyncMutualExclusion:
    def test_submit_and_poll_mutually_exclusive(self):
        """--submit and --poll cannot be used together."""
        result = _run_module(
            "--submit",
            "--poll", "abc123",
            "--prompt", "test",
        )
        data = json.loads(result.stdout)
        assert data["error"]["code"] == "MUTUAL_EXCLUSION"
        assert result.returncode != 0

    def test_submit_and_poll_all_mutually_exclusive(self):
        """--submit and --poll-all cannot be used together."""
        result = _run_module(
            "--submit",
            "--poll-all",
            "--prompt", "test",
        )
        data = json.loads(result.stdout)
        assert data["error"]["code"] == "MUTUAL_EXCLUSION"
        assert result.returncode != 0

    def test_poll_and_poll_all_mutually_exclusive(self):
        """--poll and --poll-all cannot be used together."""
        result = _run_module(
            "--poll", "abc123",
            "--poll-all",
        )
        # Both async flags present → mutual exclusion error
        data = json.loads(result.stdout)
        assert data["error"]["code"] == "MUTUAL_EXCLUSION"
        assert result.returncode != 0

