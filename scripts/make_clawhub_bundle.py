from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _safe_rmtree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _should_exclude(rel_posix: str, exclude_prefixes: tuple[str, ...], exclude_regexes: tuple[re.Pattern[str], ...]) -> bool:
    for pfx in exclude_prefixes:
        if rel_posix == pfx or rel_posix.startswith(pfx + "/"):
            return True
    for rx in exclude_regexes:
        if rx.search(rel_posix):
            return True
    return False


def _copy_tree_filtered(
    src_dir: Path,
    dst_dir: Path,
    *,
    exclude_prefixes: tuple[str, ...],
    exclude_regexes: tuple[re.Pattern[str], ...],
) -> dict[str, int]:
    counts = {"files": 0, "dirs": 0, "excluded": 0}
    src_dir = src_dir.resolve()
    dst_dir.mkdir(parents=True, exist_ok=True)

    for root, dirs, files in os.walk(src_dir):
        root_path = Path(root)
        rel_root = root_path.relative_to(src_dir).as_posix()
        if rel_root == ".":
            rel_root = ""

        if rel_root and _should_exclude(rel_root, exclude_prefixes, exclude_regexes):
            counts["excluded"] += 1
            dirs[:] = []
            continue

        if rel_root:
            (dst_dir / rel_root).mkdir(parents=True, exist_ok=True)
            counts["dirs"] += 1

        dirs_to_keep: list[str] = []
        for d in dirs:
            d_rel = f"{rel_root}/{d}" if rel_root else d
            if _should_exclude(d_rel, exclude_prefixes, exclude_regexes):
                counts["excluded"] += 1
                continue
            dirs_to_keep.append(d)
        dirs[:] = dirs_to_keep

        for f in files:
            f_rel = f"{rel_root}/{f}" if rel_root else f
            if _should_exclude(f_rel, exclude_prefixes, exclude_regexes):
                counts["excluded"] += 1
                continue
            src_file = root_path / f
            dst_file = dst_dir / f_rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            counts["files"] += 1

    return counts


def _parse_pyproject_version(pyproject: Path) -> str | None:
    try:
        import tomllib  # pyright: ignore[reportMissingImports]
    except Exception:
        tomllib = None

    if tomllib is not None:
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            v = data.get("project", {}).get("version")
            if isinstance(v, str) and v.strip():
                return v.strip()
        except Exception:
            pass

    m = re.search(r'^\s*version\s*=\s*"([^"]+)"\s*$', pyproject.read_text(encoding="utf-8"), flags=re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None


def _collect_markdown_relative_refs(markdown: str) -> list[str]:
    refs: set[str] = set()

    for m in re.finditer(r"\]\(((?:assets|references|scripts)/[^)\s#]+)", markdown):
        refs.add(m.group(1))

    for m in re.finditer(r'src\s*=\s*"(?:\./)?((?:assets|references|scripts)/[^"\s#]+)"', markdown):
        refs.add(m.group(1))

    for m in re.finditer(r"!\[[^\]]*\]\(((?:assets|references|scripts)/[^)\s#]+)", markdown):
        refs.add(m.group(1))

    return sorted(refs)


def _validate_bundle_root(bundle_root: Path) -> list[str]:
    missing: list[str] = []
    required = ["SKILL.md", "README.md", "pyproject.toml", "assets", "references", "scripts"]
    for name in required:
        if not (bundle_root / name).exists():
            missing.append(name)

    for md_name in ("SKILL.md", "README.md"):
        md_path = bundle_root / md_name
        if not md_path.exists():
            continue
        for ref in _collect_markdown_relative_refs(_read_text(md_path)):
            if not (bundle_root / ref).exists():
                missing.append(f"{md_name}: {ref}")

    return sorted(set(missing))


def _write_zip(zip_path: Path, bundle_root: Path) -> dict[str, int]:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    counts = {"files": 0}
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(bundle_root.rglob("*")):
            if p.is_dir():
                continue
            arcname = p.relative_to(bundle_root.parent).as_posix()
            zf.write(p, arcname)
            counts["files"] += 1
    return counts


def _validate_zip(zip_path: Path, bundle_name: str) -> list[str]:
    missing: list[str] = []
    must_have = f"{bundle_name}/SKILL.md"
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
    if must_have not in names:
        missing.append(must_have)
    return missing


def build_bundle(*, bundle_name: str, output_dir: Path, version: str | None, clean: bool) -> dict[str, object]:
    includes = {
        "files": ["SKILL.md", "README.md", "pyproject.toml"],
        "dirs": ["assets", "references", "scripts"],
    }

    resolved_version = version
    if resolved_version is None:
        resolved_version = _parse_pyproject_version(REPO_ROOT / "pyproject.toml")

    zip_stem = bundle_name if not resolved_version else f"{bundle_name}-{resolved_version}"
    zip_path = (output_dir / f"{zip_stem}.zip").resolve()

    staging_root = (output_dir / "publish_bundle" / bundle_name).resolve()
    if clean:
        _safe_rmtree(staging_root)
    staging_root.mkdir(parents=True, exist_ok=True)

    for f in includes["files"]:
        _copy_file(REPO_ROOT / f, staging_root / f)

    for d in ("assets", "references"):
        counts = _copy_tree_filtered(
            REPO_ROOT / d,
            staging_root / d,
            exclude_prefixes=(),
            exclude_regexes=(
                re.compile(r"(^|/)\.DS_Store$"),
                re.compile(r"(^|/)__pycache__(/|$)"),
                re.compile(r"(^|/)\.pytest_cache(/|$)"),
                re.compile(r"\.pyc$"),
            ),
        )
        includes[f"{d}_counts"] = counts

    scripts_counts = _copy_tree_filtered(
        REPO_ROOT / "scripts",
        staging_root / "scripts",
        exclude_prefixes=("tests",),
        exclude_regexes=(
            re.compile(r"(^|/)test_.*\.py$"),
            re.compile(r"(^|/)\.DS_Store$"),
            re.compile(r"(^|/)__pycache__(/|$)"),
            re.compile(r"(^|/)\.pytest_cache(/|$)"),
            re.compile(r"\.pyc$"),
        ),
    )
    includes["scripts_counts"] = scripts_counts

    missing = _validate_bundle_root(staging_root)
    zip_counts = _write_zip(zip_path, staging_root)
    zip_missing = _validate_zip(zip_path, bundle_name)

    return {
        "ok": not missing and not zip_missing,
        "bundle_name": bundle_name,
        "version": resolved_version,
        "staging_dir": str(staging_root),
        "zip_path": str(zip_path),
        "includes": includes,
        "missing": missing,
        "zip_missing": zip_missing,
        "zip_counts": zip_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a minimal ClawHub skill bundle zip (release artifact) from this repo."
    )
    parser.add_argument("--bundle-name", default="comfyui-agent-skill-mie")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "dist" / "clawhub"))
    parser.add_argument("--version", default=None)
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    _eprint(f"Repo root: {REPO_ROOT}")
    result = build_bundle(
        bundle_name=args.bundle_name,
        output_dir=Path(args.output_dir),
        version=args.version,
        clean=args.clean,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
