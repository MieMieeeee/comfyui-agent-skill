from comfyui.config import PACKAGE_ROOT


def test_package_contains_workflows_and_references():
    workflows_dir = PACKAGE_ROOT / "assets" / "workflows"
    references_dir = PACKAGE_ROOT / "references"

    assert workflows_dir.is_dir()
    assert any(workflows_dir.glob("*.config.json"))
    assert any(workflows_dir.glob("*.json"))

    assert references_dir.is_dir()
    assert (references_dir / "cli.md").exists()
    assert (references_dir / "prompt_enhancement").is_dir()
