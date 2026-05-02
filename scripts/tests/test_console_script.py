from pathlib import Path


def test_pyproject_exposes_console_script():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project.scripts]" in text
    assert 'comfyui-agent-skill-mie = "comfyui.cli:main_module"' in text
    assert 'comfyui-skill = "comfyui.cli:main_module"' in text
