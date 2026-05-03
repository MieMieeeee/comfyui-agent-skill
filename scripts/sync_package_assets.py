"""Sync root assets/ and references/ into scripts/comfyui/ (the package-internal copies).

Usage:
    python scripts/sync_package_assets.py          # sync (copy with LF normalization)
    python scripts/sync_package_assets.py --check   # report differences only, exit 1 if any
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = REPO_ROOT / "scripts" / "comfyui"

# (source relative to repo root, destination relative to package root, glob pattern)
SYNC_TRIPLETS: list[tuple[str, str, str]] = [
    ("assets/workflows", "assets/workflows", "*.json"),
    ("assets/input", "assets/input", "*.*"),
    ("assets/examples", "assets/examples", "*.*"),
    ("references", "references", "*.md"),
    ("references/prompt_enhancement", "references/prompt_enhancement", "*.md"),
]

TEXT_EXTENSIONS = {".json", ".md", ".txt", ".yaml", ".yml"}


def _normalize_lf(data: bytes) -> bytes:
    """Convert CRLF to LF."""
    return re.sub(rb"\r\n", b"\n", data)


def _read_raw(path: Path) -> bytes:
    """Read file as-is."""
    return path.read_bytes()


def _read_normalized(path: Path) -> bytes:
    """Read file and normalize line endings for text files."""
    raw = path.read_bytes()
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return _normalize_lf(raw)
    return raw


def _write_normalized(path: Path, data: bytes) -> None:
    """Write data, normalizing line endings for text files."""
    if path.suffix.lower() in TEXT_EXTENSIONS:
        data = _normalize_lf(data)
    path.write_bytes(data)


def sync(check_only: bool = False) -> int:
    changes: list[str] = []
    errors: list[str] = []

    for src_rel, dst_rel, pattern in SYNC_TRIPLETS:
        src_dir = REPO_ROOT / src_rel
        dst_dir = PACKAGE_ROOT / dst_rel

        if not src_dir.is_dir():
            continue
        dst_dir.mkdir(parents=True, exist_ok=True)

        for src_file in sorted(src_dir.rglob(pattern)):
            if src_file.is_dir():
                continue
            rel = src_file.relative_to(src_dir)
            dst_file = dst_dir / rel

            src_data = _read_normalized(src_file)

            if dst_file.exists():
                dst_data = _read_raw(dst_file)
                if src_data == dst_data:
                    continue
                if check_only:
                    changes.append(f"DIFFERS: {src_rel}/{rel}")
                else:
                    _write_normalized(dst_file, src_data)
                    changes.append(f"UPDATED: {src_rel}/{rel}")
            else:
                if check_only:
                    changes.append(f"MISSING: {src_rel}/{rel}")
                else:
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    _write_normalized(dst_file, src_data)
                    changes.append(f"CREATED: {src_rel}/{rel}")

    # Report extra files in dst that don't exist in src
    for src_rel, dst_rel, pattern in SYNC_TRIPLETS:
        src_dir = REPO_ROOT / src_rel
        dst_dir = PACKAGE_ROOT / dst_rel
        if not dst_dir.is_dir():
            continue
        for dst_file in sorted(dst_dir.rglob(pattern)):
            if dst_file.is_dir():
                continue
            rel = dst_file.relative_to(dst_dir)
            src_file = src_dir / rel
            if not src_file.exists():
                if check_only:
                    changes.append(f"ORPHAN: {dst_rel}/{rel} (not in source)")
                else:
                    dst_file.unlink()
                    changes.append(f"REMOVED: {dst_rel}/{rel} (not in source)")

    if not changes:
        print("Package assets are in sync.")
        return 0

    for line in changes:
        print(line)

    if check_only:
        print(f"\n{len(changes)} difference(s) found. Run without --check to fix.")
        return 1

    print(f"\n{len(changes)} file(s) synced.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report differences only; exit 1 if any.")
    args = parser.parse_args()
    sys.exit(sync(check_only=args.check))


if __name__ == "__main__":
    main()
