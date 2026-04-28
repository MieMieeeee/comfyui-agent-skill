#!/usr/bin/env python3
"""验证所有错误场景的测试脚本。"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from comfyui.services.workflow_config import WorkflowConfig
from comfyui.services.executor import execute_workflow
from comfyui.config import SKILL_ROOT

SERVER_URL = "http://192.168.31.120:8188"

def test_empty_prompt():
    print("\n=== Test: EMPTY_PROMPT ===")
    config = WorkflowConfig(
        workflow_id="z_image_turbo",
        workflow_file="z_image_turbo.json",
        output_node_title="Save Image",
        node_mapping={
            "prompt": {"node_title": "CLIP Text Encode (Positive Prompt)", "param": "text", "value_type": "string", "required": True},
            "seed": {"node_title": "KSampler", "param": "seed", "value_type": "integer", "auto_random": True},
            "width": {"node_title": "EmptySD3LatentImage", "param": "width", "value_type": "integer", "default": 832},
            "height": {"node_title": "EmptySD3LatentImage", "param": "height", "value_type": "integer", "default": 1280},
        },
    )
    result = execute_workflow(config, prompt="", skill_root=SKILL_ROOT, server_url=SERVER_URL)
    print(f"  success={result.success}, code={result.error['code'] if result.error else 'none'}")
    assert not result.success and result.error["code"] == "EMPTY_PROMPT", "EMPTY_PROMPT error not triggered!"
    print("  PASS")

def test_workflow_file_not_found():
    print("\n=== Test: WORKFLOW_FILE_NOT_FOUND ===")
    config = WorkflowConfig(
        workflow_id="not_exist",
        workflow_file="not_exist.json",
        output_node_title="Save Image",
        node_mapping={
            "prompt": {"node_title": "CLIP Text Encode", "param": "text", "value_type": "string"},
        },
    )
    result = execute_workflow(config, prompt="test", skill_root=SKILL_ROOT, server_url=SERVER_URL)
    print(f"  success={result.success}, code={result.error['code'] if result.error else 'none'}")
    assert not result.success and result.error["code"] == "WORKFLOW_FILE_NOT_FOUND"
    print("  PASS")

def test_mapping_not_found():
    print("\n=== Test: MAPPING_NOT_FOUND ===")
    config = WorkflowConfig(
        workflow_id="bad_mapping",
        workflow_file="z_image_turbo.json",
        output_node_title="Save Image",
        node_mapping={},  # no prompt mapping
    )
    result = execute_workflow(config, prompt="test", skill_root=SKILL_ROOT, server_url=SERVER_URL)
    print(f"  success={result.success}, code={result.error['code'] if result.error else 'none'}")
    assert not result.success and result.error["code"] == "MAPPING_NOT_FOUND"
    print("  PASS")

def test_bad_model():
    print("\n=== Test: EXECUTION_FAILED (bad model name) ===")
    import json, copy
    wf_path = SKILL_ROOT / "assets" / "workflows" / "z_image_turbo.json"
    wf_data = json.loads(wf_path.read_text(encoding="utf-8"))
    wf_data["16"]["inputs"]["unet_name"] = "nonexistent_model.safetensors"
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(wf_data, f)
        bad_wf_path = Path(f.name)
    try:
        config = WorkflowConfig(
            workflow_id="bad_model",
            workflow_file=bad_wf_path.name,
            output_node_title="Save Image",
            node_mapping={
                "prompt": {"node_title": "CLIP Text Encode (Positive Prompt)", "param": "text", "value_type": "string"},
                "seed": {"node_title": "KSampler", "param": "seed", "value_type": "integer", "auto_random": True},
                "width": {"node_title": "EmptySD3LatentImage", "param": "width", "value_type": "integer", "default": 832},
                "height": {"node_title": "EmptySD3LatentImage", "param": "height", "value_type": "integer", "default": 1280},
            },
        )
        config.resolve_workflow_path = lambda root: bad_wf_path
        result = execute_workflow(config, prompt="test", skill_root=SKILL_ROOT, server_url=SERVER_URL)
        print(f"  success={result.success}, code={result.error['code'] if result.error else 'none'}")
        assert not result.success and result.error["code"] == "EXECUTION_FAILED"
        print("  PASS")
    finally:
        bad_wf_path.unlink(missing_ok=True)

def test_bad_vae():
    print("\n=== Test: EXECUTION_FAILED (bad VAE name) ===")
    import json
    wf_path = SKILL_ROOT / "assets" / "workflows" / "z_image_turbo.json"
    wf_data = json.loads(wf_path.read_text(encoding="utf-8"))
    wf_data["17"]["inputs"]["vae_name"] = "nonexistent_vae.sft"
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(wf_data, f)
        bad_wf_path = Path(f.name)
    try:
        config = WorkflowConfig(
            workflow_id="bad_vae",
            workflow_file=bad_wf_path.name,
            output_node_title="Save Image",
            node_mapping={
                "prompt": {"node_title": "CLIP Text Encode (Positive Prompt)", "param": "text", "value_type": "string"},
                "seed": {"node_title": "KSampler", "param": "seed", "value_type": "integer", "auto_random": True},
                "width": {"node_title": "EmptySD3LatentImage", "param": "width", "value_type": "integer", "default": 832},
                "height": {"node_title": "EmptySD3LatentImage", "param": "height", "value_type": "integer", "default": 1280},
            },
        )
        config.resolve_workflow_path = lambda root: bad_wf_path
        result = execute_workflow(config, prompt="test", skill_root=SKILL_ROOT, server_url=SERVER_URL)
        print(f"  success={result.success}, code={result.error['code'] if result.error else 'none'}")
        assert not result.success and result.error["code"] == "EXECUTION_FAILED"
        print("  PASS")
    finally:
        bad_wf_path.unlink(missing_ok=True)

def test_bad_clip():
    print("\n=== Test: EXECUTION_FAILED (bad CLIP name) ===")
    import json
    wf_path = SKILL_ROOT / "assets" / "workflows" / "z_image_turbo.json"
    wf_data = json.loads(wf_path.read_text(encoding="utf-8"))
    wf_data["18"]["inputs"]["clip_name"] = "nonexistent_clip.safetensors"
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(wf_data, f)
        bad_wf_path = Path(f.name)
    try:
        config = WorkflowConfig(
            workflow_id="bad_clip",
            workflow_file=bad_wf_path.name,
            output_node_title="Save Image",
            node_mapping={
                "prompt": {"node_title": "CLIP Text Encode (Positive Prompt)", "param": "text", "value_type": "string"},
                "seed": {"node_title": "KSampler", "param": "seed", "value_type": "integer", "auto_random": True},
                "width": {"node_title": "EmptySD3LatentImage", "param": "width", "value_type": "integer", "default": 832},
                "height": {"node_title": "EmptySD3LatentImage", "param": "height", "value_type": "integer", "default": 1280},
            },
        )
        config.resolve_workflow_path = lambda root: bad_wf_path
        result = execute_workflow(config, prompt="test", skill_root=SKILL_ROOT, server_url=SERVER_URL)
        print(f"  success={result.success}, code={result.error['code'] if result.error else 'none'}")
        assert not result.success and result.error["code"] == "EXECUTION_FAILED"
        print("  PASS")
    finally:
        bad_wf_path.unlink(missing_ok=True)

def test_wrong_output_node():
    print("\n=== Test: NO_OUTPUT (wrong output node title) ===")
    config = WorkflowConfig(
        workflow_id="wrong_node",
        workflow_file="z_image_turbo.json",
        output_node_title="NonExistentNode",
        node_mapping={
            "prompt": {"node_title": "CLIP Text Encode (Positive Prompt)", "param": "text", "value_type": "string"},
            "seed": {"node_title": "KSampler", "param": "seed", "value_type": "integer", "auto_random": True},
            "width": {"node_title": "EmptySD3LatentImage", "param": "width", "value_type": "integer", "default": 832},
            "height": {"node_title": "EmptySD3LatentImage", "param": "height", "value_type": "integer", "default": 1280},
        },
    )
    result = execute_workflow(config, prompt="a cat", skill_root=SKILL_ROOT, server_url=SERVER_URL)
    print(f"  success={result.success}, code={result.error['code'] if result.error else 'none'}")
    assert not result.success and result.error["code"] == "NO_OUTPUT"
    print("  PASS")

def test_missing_input_image():
    print("\n=== Test: NO_INPUT_IMAGE (required image not provided) ===")
    config = WorkflowConfig(
        workflow_id="needs_image",
        workflow_file="z_image_turbo.json",
        output_node_title="Save Image",
        capability="image_to_image",
        node_mapping={
            "prompt": {"node_title": "CLIP Text Encode (Positive Prompt)", "param": "text", "value_type": "string"},
            "input_image": {"node_title": "LoadImage", "param": "image", "value_type": "image", "required": True},
        },
    )
    result = execute_workflow(config, prompt="test", skill_root=SKILL_ROOT, server_url=SERVER_URL)
    print(f"  success={result.success}, code={result.error['code'] if result.error else 'none'}")
    assert not result.success and result.error["code"] == "NO_INPUT_IMAGE"
    print("  PASS")

def test_input_image_not_found():
    print("\n=== Test: INPUT_IMAGE_NOT_FOUND ===")
    config = WorkflowConfig(
        workflow_id="needs_image",
        workflow_file="z_image_turbo.json",
        output_node_title="Save Image",
        capability="image_to_image",
        node_mapping={
            "prompt": {"node_title": "CLIP Text Encode (Positive Prompt)", "param": "text", "value_type": "string"},
            "input_image": {"node_title": "LoadImage", "param": "image", "value_type": "image", "required": True},
        },
    )
    result = execute_workflow(
        config, prompt="test", skill_root=SKILL_ROOT, server_url=SERVER_URL,
        input_images={"input_image": Path("E:/nonexistent/image.png")}
    )
    print(f"  success={result.success}, code={result.error['code'] if result.error else 'none'}")
    assert not result.success and result.error["code"] == "INPUT_IMAGE_NOT_FOUND"
    print("  PASS")

if __name__ == "__main__":
    tests = [
        test_empty_prompt,
        test_workflow_file_not_found,
        test_mapping_not_found,
        test_wrong_output_node,
        test_missing_input_image,
        test_input_image_not_found,
        test_bad_model,
        test_bad_vae,
        test_bad_clip,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1
    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    sys.exit(0 if failed == 0 else 1)
