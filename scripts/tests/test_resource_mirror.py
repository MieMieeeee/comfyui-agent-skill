from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE_ROOT = (SKILL_ROOT / "scripts" / "comfyui").resolve()


def _pairs(src_root: Path, dst_root: Path, pattern: str) -> list[tuple[Path, Path]]:
    out: list[tuple[Path, Path]] = []
    for src in sorted(src_root.rglob(pattern)):
        rel = src.relative_to(src_root)
        out.append((src, dst_root / rel))
    return out


def test_assets_workflows_mirrored_into_package():
    src_root = SKILL_ROOT / "assets" / "workflows"
    dst_root = PACKAGE_ROOT / "assets" / "workflows"
    assert src_root.is_dir()
    assert dst_root.is_dir()

    for src, dst in _pairs(src_root, dst_root, "*.json"):
        assert dst.exists()
        assert src.read_bytes() == dst.read_bytes()


def test_references_mirrored_into_package():
    src_root = SKILL_ROOT / "references"
    dst_root = PACKAGE_ROOT / "references"
    assert src_root.is_dir()
    assert dst_root.is_dir()

    for src, dst in _pairs(src_root, dst_root, "*.md"):
        assert dst.exists()
        assert src.read_bytes() == dst.read_bytes()
