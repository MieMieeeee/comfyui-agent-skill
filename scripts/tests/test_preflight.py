"""Preflight validation: mocked red/green + optional live ComfyUI.

Mock tests always run (no real Comfy required).
Live tests run only when GET /system_stats succeeds on resolved COMFYUI_URL / config.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import pytest

from comfyui.config import check_server, get_comfyui_url
from comfyui.preflight import (
    collect_class_types,
    extract_model_references,
    validate_workflow_resources,
    load_workflow_json,
)


# --- Minimal workflows for mocks ---
WF_NODE_OK = {
    "3": {"class_type": "KSampler", "inputs": {}},
}

WF_NODE_BAD = {
    "3": {"class_type": "KSampler", "inputs": {}},
    "99": {"class_type": "DefinitelyMissingNodeClass_XYZ", "inputs": {}},
}

WF_MODEL_OK = {
    "16": {
        "class_type": "UNETLoader",
        "inputs": {"unet_name": "models/unet_example.safetensors", "weight_dtype": "default"},
    },
}

WF_MODEL_BAD = {
    "16": {
        "class_type": "UNETLoader",
        "inputs": {"unet_name": "ghost/nope_missing.safetensors", "weight_dtype": "default"},
    },
}

WF_LORA_OK = {
    "16": {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {"lora_name": "LTX-2/lora_example.safetensors", "strength_model": 1},
    },
}

WF_LORA_BAD = {
    "16": {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {"lora_name": "ghost/nope_lora_missing.safetensors", "strength_model": 1},
    },
}

WF_DUALCLIP_OK = {
    "16": {
        "class_type": "DualCLIPLoader",
        "inputs": {"clip_name1": "LTX-2/clip1_example.safetensors", "clip_name2": "LTX-2/clip2_example.safetensors"},
    },
}


def _make_object_info(include_missing: bool = True) -> dict:
    """KSampler always present; Fake missing node only when include_missing."""
    base = {
        "KSampler": {"input": {}, "output": [], "name": "KSampler"},
        "UNETLoader": {"input": {}, "output": [], "name": "UNETLoader"},
        "LoraLoaderModelOnly": {"input": {}, "output": [], "name": "LoraLoaderModelOnly"},
        "DualCLIPLoader": {"input": {}, "output": [], "name": "DualCLIPLoader"},
    }
    if include_missing:
        base["DefinitelyMissingNodeClass_XYZ"] = {"input": {}, "output": [], "name": "DefinitelyMissingNodeClass_XYZ"}
    return base


class _PreflightMockHandler(BaseHTTPRequestHandler):
    """Configurable: scenario 'green_nodes' | 'red_missing_node' | 'green_models' | 'red_missing_model'."""

    scenario = "green_nodes"

    def do_GET(self) -> None:
        if self.path == "/object_info":
            if self.scenario == "red_missing_node":
                body = json.dumps({"KSampler": _make_object_info(False)["KSampler"]}).encode()
            else:
                body = json.dumps(_make_object_info(True)).encode()
        elif self.path == "/models":
            body = json.dumps(["models"]).encode()
        elif self.path == "/models/models":
            if self.scenario == "red_missing_model":
                body = json.dumps([]).encode()
            else:
                body = json.dumps(
                    [
                        "unet_example.safetensors",
                        "lora_example.safetensors",
                        "clip1_example.safetensors",
                        "clip2_example.safetensors",
                    ]
                ).encode()
        elif self.path == "/system_stats":
            body = json.dumps({"system": {"ram_total": 1}}).encode()
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _run_mock_server(scenario: str) -> tuple[str, HTTPServer]:
    _PreflightMockHandler.scenario = scenario
    server = HTTPServer(("127.0.0.1", 0), _PreflightMockHandler)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return f"http://127.0.0.1:{port}", server


# ----- Mocked: GREEN -----
class TestPreflightMockGreen:
    """Assert ok=True when mock server satisfies workflow."""

    def test_nodes_only_workflow_all_registered(self):
        url, srv = _run_mock_server("green_nodes")
        try:
            r = validate_workflow_resources(url, WF_NODE_OK)
            assert r.ok is True
            assert r.server_reachable is True
            assert r.missing_node_types == []
            assert r.error is None
        finally:
            srv.shutdown()

    def test_unet_model_present_in_models_api(self):
        url, srv = _run_mock_server("green_models")
        try:
            r = validate_workflow_resources(url, WF_MODEL_OK)
            assert r.ok is True
            assert r.missing_models == []
            assert r.error is None
        finally:
            srv.shutdown()

    def test_lora_model_present_in_models_api(self):
        url, srv = _run_mock_server("green_models")
        try:
            r = validate_workflow_resources(url, WF_LORA_OK)
            assert r.ok is True
            assert r.missing_models == []
            assert r.error is None
        finally:
            srv.shutdown()

    def test_dualclip_models_present_in_models_api(self):
        url, srv = _run_mock_server("green_models")
        try:
            r = validate_workflow_resources(url, WF_DUALCLIP_OK)
            assert r.ok is True
            assert r.missing_models == []
            assert r.error is None
        finally:
            srv.shutdown()


# ----- Mocked: RED -----
class TestPreflightMockRed:
    """Assert ok=False when mock server lacks node or model."""

    def test_missing_custom_node_type(self):
        url, srv = _run_mock_server("red_missing_node")
        try:
            r = validate_workflow_resources(url, WF_NODE_BAD)
            assert r.ok is False
            assert r.server_reachable is True
            assert "DefinitelyMissingNodeClass_XYZ" in r.missing_node_types
            assert r.error == "missing_node_types"
        finally:
            srv.shutdown()

    def test_missing_model_file_listing(self):
        url, srv = _run_mock_server("red_missing_model")
        try:
            r = validate_workflow_resources(url, WF_MODEL_BAD)
            assert r.ok is False
            assert r.missing_models
            assert r.error == "missing_models"
        finally:
            srv.shutdown()

    def test_missing_lora_model_file_listing(self):
        url, srv = _run_mock_server("red_missing_model")
        try:
            r = validate_workflow_resources(url, WF_LORA_BAD)
            assert r.ok is False
            assert r.missing_models
            assert r.error == "missing_models"
        finally:
            srv.shutdown()

    def test_dead_server_not_reachable(self):
        r = validate_workflow_resources("http://127.0.0.1:59998", WF_NODE_OK)
        assert r.ok is False
        assert r.server_reachable is False
        assert r.error is not None


# ----- Helpers unit tests -----
class TestPreflightHelpers:
    def test_collect_class_types(self):
        wf = {"a": {"class_type": "Foo"}, "b": {"class_type": "Bar"}, "c": {}}
        assert collect_class_types(wf) == {"Foo", "Bar"}

    def test_extract_model_references_unet(self):
        wf = WF_MODEL_OK
        refs = extract_model_references(wf)
        assert "models/unet_example.safetensors" in refs

    def test_extract_model_references_lora_model_only(self):
        refs = extract_model_references(WF_LORA_OK)
        assert "LTX-2/lora_example.safetensors" in refs

    def test_extract_model_references_dualclip(self):
        refs = extract_model_references(WF_DUALCLIP_OK)
        assert "LTX-2/clip1_example.safetensors" in refs
        assert "LTX-2/clip2_example.safetensors" in refs


# ----- Live (skip when Comfy down): GREEN vs RED -----
_live_url = get_comfyui_url().rstrip("/")
_live_up = check_server(_live_url)["available"]

requires_live_comfy = pytest.mark.skipif(
    not _live_up,
    reason=f"ComfyUI not reachable at {_live_url} (GET /system_stats)",
)


@requires_live_comfy
class TestPreflightLiveGreen:
    """Real server: z_image workflow nodes should all register — GREEN when env matches docs."""

    def test_z_image_all_node_types_exist(self, skill_root: Path):
        path = skill_root / "assets" / "workflows" / "z_image_turbo.json"
        wf = load_workflow_json(path)
        r = validate_workflow_resources(_live_url, wf)
        assert r.server_reachable is True, r.error
        assert r.missing_node_types == [], f"missing nodes: {r.missing_node_types}"
        if r.missing_models:
            pytest.skip(
                f"GET /models 未包含工作流所需权重（可安装模型后再跑全绿）: {r.missing_models}"
            )
        assert r.ok is True


@requires_live_comfy
class TestPreflightLiveRedContrast:
    """Same validator on a dead port — RED."""

    def test_unreachable_port_returns_not_ok(self, skill_root: Path):
        path = skill_root / "assets" / "workflows" / "z_image_turbo.json"
        wf = load_workflow_json(path)
        r = validate_workflow_resources("http://127.0.0.1:59997", wf)
        assert r.ok is False
        assert r.server_reachable is False
