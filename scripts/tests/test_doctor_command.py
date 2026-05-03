from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


def test_cli_admin_exposes_doctor_command():
    import comfyui.cli_admin as cli_admin

    assert hasattr(cli_admin, "cmd_doctor")


def test_doctor_aggregates_preflight_results(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    from comfyui.preflight import PreflightResult
    from comfyui.services.workflow_config import WorkflowConfig

    import comfyui.cli_admin as cli_admin
    import comfyui.config as config
    import comfyui.preflight as preflight
    import comfyui.services.workflow_config as workflow_config

    monkeypatch.setattr(
        cli_admin,
        "check_server",
        lambda url: {"available": True, "url": url, "stats": {"ok": True}},
    )
    monkeypatch.setattr(config, "get_workflows_dir", lambda: tmp_path)

    workflow_config.WORKFLOW_REGISTRY = {
        "wf_ok": WorkflowConfig(workflow_id="wf_ok", workflow_file="wf_ok.json", output_node_title="Save Image"),
        "wf_bad": WorkflowConfig(workflow_id="wf_bad", workflow_file="wf_bad.json", output_node_title="Save Image"),
    }

    (tmp_path / "wf_ok.json").write_text("{}", encoding="utf-8")
    (tmp_path / "wf_bad.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(preflight, "preflight_registered_workflow", lambda server_url, workflow_path: PreflightResult(ok=True, server_reachable=True))

    def _fake_preflight(server_url: str, workflow_path: Path) -> PreflightResult:
        if workflow_path.name == "wf_bad.json":
            return PreflightResult(ok=False, server_reachable=True, missing_models=[{"path": "models/a.safetensors", "type": "diffusion_model", "folder": "diffusion_models"}], error="missing_models")
        return PreflightResult(ok=True, server_reachable=True)

    monkeypatch.setattr(preflight, "preflight_registered_workflow", _fake_preflight)

    argv0 = sys.argv[0]
    try:
        sys.argv = [argv0, "--server", "http://127.0.0.1:8188"]
        rc = cli_admin.cmd_doctor()
    finally:
        sys.argv = [argv0]

    assert rc == 1
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["server"]["available"] is True
    assert payload["success"] is False
    assert set(payload["workflows_checked"]) == {"wf_ok", "wf_bad"}
    assert payload["workflows"]["wf_ok"]["success"] is True
    assert payload["workflows"]["wf_bad"]["success"] is False
    assert len(payload["summary"]["missing_models"]) == 1
    assert payload["summary"]["missing_models"][0]["path"] == "models/a.safetensors"


def test_doctor_handles_missing_workflow_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    from comfyui.services.workflow_config import WorkflowConfig

    import comfyui.cli_admin as cli_admin
    import comfyui.config as config
    import comfyui.services.workflow_config as workflow_config

    monkeypatch.setattr(
        cli_admin,
        "check_server",
        lambda url: {"available": True, "url": url, "stats": {"ok": True}},
    )
    monkeypatch.setattr(config, "get_workflows_dir", lambda: tmp_path)

    workflow_config.WORKFLOW_REGISTRY = {
        "wf_missing": WorkflowConfig(workflow_id="wf_missing", workflow_file="wf_missing.json", output_node_title="Save Image"),
    }

    argv0 = sys.argv[0]
    try:
        sys.argv = [argv0, "--server", "http://127.0.0.1:8188"]
        rc = cli_admin.cmd_doctor()
    finally:
        sys.argv = [argv0]

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    wf = payload["workflows"]["wf_missing"]
    assert wf["success"] is False
    assert wf["error"]["code"] == "WORKFLOW_FILE_NOT_FOUND"
