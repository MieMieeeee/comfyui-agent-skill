import tomllib
from pathlib import Path


def test_pyproject_exposes_console_script():
    root = Path(__file__).resolve().parent.parent.parent
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = (data.get("project") or {}).get("scripts") or {}
    assert scripts.get("comfyui-skill") == "comfyui.cli:main_module"
