from pathlib import Path


def test_readme_has_quickstart_troubleshooting_and_short_cli():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "README.md").read_text(encoding="utf-8")
    assert "Quick Start" in text or "Quickstart" in text
    assert "Troubleshooting" in text
    assert "SERVER_UNAVAILABLE" in text
    assert "PREFLIGHT_MISSING_NODES" in text
    assert "NO_OUTPUT" in text
    assert "comfyui-skill" in text


def test_maintainer_mentions_import_workflow():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "MAINTAINER.md").read_text(encoding="utf-8")
    assert "import-workflow" in text


def test_cli_reference_mentions_import_workflow():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "references" / "cli.md").read_text(encoding="utf-8")
    assert "import-workflow" in text
