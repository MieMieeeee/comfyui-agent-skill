"""Ensure vendored comfy_api_simplified is used (no missing git+ install)."""
from pathlib import Path

from comfy_api_simplified import ComfyApiWrapper


def test_vendored_package_lives_under_scripts() -> None:
    import comfy_api_simplified

    root = Path(comfy_api_simplified.__file__).resolve().parent
    assert root.name == "comfy_api_simplified"
    assert (root / "api.py").is_file()
    assert (root / "workflow.py").is_file()
    assert (root / "exceptions.py").is_file()
    assert (root / "LICENSE").is_file()


def test_comfy_api_wrapper_instantiates() -> None:
    api = ComfyApiWrapper("http://127.0.0.1:8188")
    assert "8188" in api.url
