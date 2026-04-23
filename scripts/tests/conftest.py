"""Shared fixtures for comfyui skill tests."""
from pathlib import Path

import pytest

# Ensure the scripts/ directory is on sys.path so the comfyui package is importable.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
SKILL_ROOT = SCRIPTS_DIR.parent

import sys

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def skill_root():
    return SKILL_ROOT


@pytest.fixture
def workflow_path(skill_root):
    return skill_root / "assets" / "workflows" / "z_image_turbo.json"
