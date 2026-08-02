"""Tests for UI/Save <-> API format classification and the convert-ui wiring.

The Playwright-driven conversion itself needs a live ComfyUI + browser, so it
is not exercised here. We cover the dependency-free classifier, the batch
output-path mapping, the single-file CLI branches that run *before* Playwright
is touched, and the import refusal of non-API input.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from comfyui.tools.convert_ui_workflow import (
    FORMAT_API,
    FORMAT_UI,
    WorkflowFormatError,
    _relative_output_path,
    classify_workflow_format,
    load_and_classify,
)

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = (SKILL_ROOT / "scripts").resolve()
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _run_module(*args: str, extra_env: dict | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(SCRIPTS_DIR), **(extra_env or {})}
    return subprocess.run(
        [sys.executable, "-m", "comfyui", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or SKILL_ROOT),
        env=env,
    )


class TestClassify:
    def test_classify_ui_format(self):
        data = json.loads((FIXTURES / "ui_format.json").read_text(encoding="utf-8"))
        assert classify_workflow_format(data) == FORMAT_UI

    def test_classify_api_format(self):
        data = {
            "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "a cat"}},
            "2": {"class_type": "SaveImage", "inputs": {}},
        }
        assert classify_workflow_format(data) == FORMAT_API

    def test_classify_unknown_for_non_dict(self):
        assert classify_workflow_format([1, 2, 3]) == "unknown"
        assert classify_workflow_format("not a workflow") == "unknown"

    def test_classify_unknown_for_arbitrary_dict(self):
        assert classify_workflow_format({"foo": "bar"}) == "unknown"

    def test_classify_unknown_when_only_nodes_present(self):
        # Front-end requires BOTH nodes and links to treat as UI/Save.
        assert classify_workflow_format({"nodes": []}) == "unknown"

    def test_api_requires_every_value_to_have_class_type_and_inputs(self):
        # One malformed entry -> not API. Not UI either (no nodes/links) -> unknown.
        data = {
            "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "a cat"}},
            "2": {"class_type": "SaveImage"},  # missing inputs
        }
        assert classify_workflow_format(data) == "unknown"

    def test_load_and_classify_raises_on_bad_json(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(ValueError):
            load_and_classify(bad)

    def test_load_and_classify_roundtrip(self):
        fmt, _ = load_and_classify(FIXTURES / "ui_format.json")
        assert fmt == FORMAT_UI


class TestRelativeOutputPath:
    def test_preserves_subtree(self, tmp_path: Path):
        src_root = tmp_path / "src"
        out_root = tmp_path / "out"
        src_file = src_root / "sub" / "deep" / "Krea.json"
        src_file.parent.mkdir(parents=True)
        src_file.write_text("{}", encoding="utf-8")

        got = _relative_output_path(src_root, src_file, out_root)
        assert got == out_root / "sub" / "deep" / "Krea.json"

    def test_normalizes_extension(self, tmp_path: Path):
        src_root = tmp_path / "src"
        out_root = tmp_path / "out"
        src_file = src_root / "a.txt"
        src_file.parent.mkdir(parents=True)
        src_file.write_text("{}", encoding="utf-8")
        got = _relative_output_path(src_root, src_file, out_root)
        assert got.suffix == ".json"


class TestConvertUiCliRouting:
    """The pre-Playwright branches of `convert-ui` must work offline."""

    def test_source_not_found(self, tmp_path: Path):
        r = _run_module("convert-ui", str(tmp_path / "missing.json"), "--server", "http://x:1")
        assert r.returncode != 0
        data = json.loads(r.stdout)
        assert data["success"] is False
        assert data["error"]["code"] == "SOURCE_NOT_FOUND"

    def test_skips_already_api_format(self, tmp_path: Path):
        src = tmp_path / "already_api.json"
        src.write_text(
            json.dumps(
                {"1": {"class_type": "SaveImage", "inputs": {}}},
            ),
            encoding="utf-8",
        )
        r = _run_module("convert-ui", str(src), "-o", str(tmp_path / "out.json"), "--server", "http://x:1")
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        assert data["status"] == "skipped_api"

    def test_rejects_neither_ui_nor_api(self, tmp_path: Path):
        src = tmp_path / "weird.json"
        src.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
        r = _run_module("convert-ui", str(src), "-o", str(tmp_path / "out.json"), "--server", "http://x:1")
        assert r.returncode != 0
        data = json.loads(r.stdout)
        assert data["error"]["code"] == "WORKFLOW_NOT_UI_FORMAT"

    def test_subcommand_is_listed_in_help(self):
        r = _run_module("--help")
        assert "convert-ui" in r.stderr

    def test_unknown_subcommand_message_lists_convert_ui(self):
        r = _run_module("nope")
        assert "convert-ui" in r.stderr
