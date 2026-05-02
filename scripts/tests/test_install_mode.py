import json
import os
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = (SKILL_ROOT / "scripts").resolve()


def _run_module_from_cwd(cwd: Path, *args: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(SCRIPTS_DIR), **(extra_env or {})}
    return subprocess.run(
        [sys.executable, "-m", "comfyui", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=env,
    )


class TestInstallModeCwdIndependent:
    def test_generate_preflight_works_outside_repo_cwd(self, tmp_path):
        env = {
            "COMFYUI_SKILL_RESOURCE_ROOT": str(SCRIPTS_DIR / "comfyui"),
            "COMFYUI_SKILL_USER_DATA_ROOT": str(tmp_path / "user_data"),
        }
        r = _run_module_from_cwd(
            tmp_path,
            "generate",
            "--preflight",
            "--workflow",
            "z_image_turbo",
            "--server",
            "http://127.0.0.1:59997",
            extra_env=env,
        )
        assert r.returncode == 1
        data = json.loads(r.stdout)
        assert data["success"] is False
        assert data["workflow_id"] == "z_image_turbo"
        assert data["error"]["code"] == "PREFLIGHT_SERVER_UNREACHABLE"

    def test_save_server_writes_to_user_data_root(self, tmp_path):
        user_root = tmp_path / "user_data"
        env = {
            "COMFYUI_SKILL_RESOURCE_ROOT": str(SCRIPTS_DIR / "comfyui"),
            "COMFYUI_SKILL_USER_DATA_ROOT": str(user_root),
        }
        r = _run_module_from_cwd(tmp_path, "save-server", "http://127.0.0.1:8188", extra_env=env)
        assert r.returncode == 0
        payload = json.loads(r.stdout)
        assert payload["saved"] is True
        assert Path(payload["config_file"]).resolve() == (user_root / "config.local.json").resolve()
        assert (user_root / "config.local.json").exists()
