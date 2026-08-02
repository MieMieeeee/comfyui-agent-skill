"""Classify ComfyUI workflow JSON and convert UI/Save format to API format.

Two responsibilities, kept intentionally separate:

1. :func:`classify_workflow_format` — pure-python, dependency-free classifier
   that tells UI/Save format (litegraph ``{nodes, links}``) from API format
   (``{"1": {"class_type": ..., "inputs": ...}}``). Used by
   :func:`import_workflow` to refuse non-API input with a helpful message
   instead of crashing inside :func:`analyze_workflow`.

2. :func:`convert_ui_to_api` / :func:`convert_ui_workflows_dir` — opt-in
   conversion that drives a running ComfyUI front-end via Playwright. This
   mirrors the approach in ``docs/convert_ui_workflows.md``: reuse the
   authoritative front-end implementation (``loadGraphData`` +
   ``graphToPrompt``) rather than re-implementing the rules in Python.
   Playwright is imported lazily so the rest of the skill stays dependency-free.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Format classification (dependency-free)
# ---------------------------------------------------------------------------

FORMAT_UI = "ui"
FORMAT_API = "api"
FORMAT_UNKNOWN = "unknown"


class WorkflowFormatError(ValueError):
    """Raised when a workflow JSON is not in the API format expected by import/analyze."""


def classify_workflow_format(data: Any) -> str:
    """Classify a parsed workflow JSON as ``ui``, ``api`` or ``unknown``.

    Rules mirror the front-end ``getDataFromJSON`` dispatch documented in
    ``docs/convert_ui_workflows.md``:

    - **ui**: top-level dict with both ``nodes`` and ``links`` keys — the
      ComfyUI *Save* button product (litegraph graph).
    - **api**: top-level dict where *every* value has ``class_type`` and
      ``inputs`` — the ComfyUI *Save (API)* button product.
    - **unknown**: anything else (including non-dict payloads).
    """
    if not isinstance(data, dict):
        return FORMAT_UNKNOWN

    if "nodes" in data and "links" in data:
        return FORMAT_UI

    if data and all(isinstance(v, dict) and "class_type" in v and "inputs" in v for v in data.values()):
        return FORMAT_API

    return FORMAT_UNKNOWN


def load_and_classify(path: Path) -> tuple[str, Any]:
    """Read ``path`` as JSON and return ``(format, parsed)``.

    Raises :class:`ValueError` on JSON decode failure (caller maps it to
    ``WORKFLOW_JSON_INVALID``).
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid workflow json: {e}") from e
    return classify_workflow_format(data), data


# ---------------------------------------------------------------------------
# Conversion via Playwright (opt-in, lazily imported)
# ---------------------------------------------------------------------------

# Browser-side script. Kept as a constant so it is trivial to audit.
# Mirrors the verified snippet in docs/convert_ui_workflows.md §3.
_CONVERT_SCRIPT = """
async (uiData) => {
    const app = window.comfyAPI.app.app;
    app.canvas.setGraph(app.rootGraph);
    await app.loadGraphData(uiData, true, false, null, {
        checkForRerouteMigration: true,
        deferWarnings: true,
        skipAssetScans: true,
        silentAssetErrors: true
    });
    const converted = await app.graphToPrompt();
    return converted.output;
}
"""

# Graph-readiness predicates used as page.wait_for_function arguments.
_GRAPH_READY = "window.comfyAPI && window.comfyAPI.app && window.comfyAPI.app.app && window.comfyAPI.app.app.graph"
_NODE_TABLE_READY = "Object.keys(window.LiteGraph?.registered_node_types ?? {}).length > 0"


@dataclass
class ConversionResult:
    """Per-file outcome of a batch conversion."""

    path: str
    status: str  # converted | skipped_api | skipped_unknown | failed
    output: str | None = None
    ui_nodes: int | None = None
    api_nodes: int | None = None
    error: str | None = None


@dataclass
class BatchReport:
    """Aggregate report for :func:`convert_ui_workflows_dir`."""

    source_root: str
    output_root: str
    comfy_url: str
    total: int = 0
    results: list[ConversionResult] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        c: dict[str, int] = {}
        for r in self.results:
            c[r.status] = c.get(r.status, 0) + 1
        return c

    @property
    def failures(self) -> list[ConversionResult]:
        return [r for r in self.results if r.status == "failed"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_root": self.source_root,
            "output_root": self.output_root,
            "comfy_url": self.comfy_url,
            "total": self.total,
            "counts": self.counts,
            "failures": [
                {"path": f.path, "error": f.error} for f in self.failures
            ],
            "results": [r.__dict__ for r in self.results],
        }


def _relative_output_path(src_root: Path, src_file: Path, output_root: Path) -> Path:
    """Map a source file to its mirror under ``output_root``, preserving subtree layout."""
    rel = src_file.relative_to(src_root)
    return (output_root / rel).with_suffix(".json")


def convert_ui_to_api(
    ui_data: dict,
    *,
    comfy_url: str,
    timeout_ms: int = 120_000,
) -> tuple[dict, int]:
    """Convert a single UI/Save workflow dict to API format via ComfyUI front-end.

    Returns ``(api_json, ui_node_count)``.

    Requires Playwright + Chromium and a reachable ComfyUI server. Imported
    lazily so the module is import-safe without those deps.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:  # pragma: no cover - exercised only without playwright
        raise RuntimeError(
            "Playwright is required for UI->API conversion. "
            "Install it with: pip install playwright && playwright install chromium"
        ) from e

    ui_node_count = len(ui_data.get("nodes", []))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.goto(comfy_url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_function(_GRAPH_READY, timeout=timeout_ms)
            page.wait_for_function(_NODE_TABLE_READY, timeout=timeout_ms)

            api_json = page.evaluate(_CONVERT_SCRIPT, ui_data)
        finally:
            browser.close()

    if not isinstance(api_json, dict):
        raise RuntimeError("front-end returned non-dict API output")
    return api_json, ui_node_count


def convert_ui_workflows_dir(
    source: Path,
    output: Path,
    *,
    comfy_url: str,
    timeout_ms: int = 120_000,
) -> BatchReport:
    """Batch-convert every UI/Save workflow under ``source`` to API format.

    - UI files are converted and written to ``output`` mirroring the subtree.
    - API files are skipped (``skipped_api``).
    - Unknown/unparseable files are skipped (``skipped_unknown``).
    - A single-file failure never aborts the batch; it is recorded as ``failed``.
    """
    source = source.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    report = BatchReport(source_root=str(source), output_root=str(output), comfy_url=comfy_url)
    files = sorted(p for p in source.rglob("*.json") if output not in p.parents and output != p.parent)

    for src_file in files:
        rel = str(src_file.relative_to(source))
        try:
            fmt, data = load_and_classify(src_file)
        except ValueError as e:
            report.results.append(ConversionResult(path=rel, status="skipped_unknown", error=str(e)))
            report.total += 1
            continue

        if fmt == FORMAT_API:
            report.results.append(ConversionResult(path=rel, status="skipped_api"))
            report.total += 1
            continue
        if fmt == FORMAT_UNKNOWN:
            report.results.append(ConversionResult(path=rel, status="skipped_unknown"))
            report.total += 1
            continue

        # fmt == FORMAT_UI
        try:
            api_json, ui_nodes = convert_ui_to_api(data, comfy_url=comfy_url, timeout_ms=timeout_ms)
            dst = _relative_output_path(source, src_file, output)
            dst.parent.mkdir(parents=True, exist_ok=True)
            # IMPORTANT: write converted.output verbatim, no {"prompt": ...} wrapper.
            # A wrapper makes ComfyUI treat it as UI/Save -> "Empty canvas" on drag-in.
            dst.write_text(json.dumps(api_json, ensure_ascii=False, indent=2), encoding="utf-8")
            report.results.append(
                ConversionResult(
                    path=rel,
                    status="converted",
                    output=str(dst),
                    ui_nodes=ui_nodes,
                    api_nodes=len(api_json),
                )
            )
        except Exception as e:  # single-file failure must not abort the batch
            report.results.append(ConversionResult(path=rel, status="failed", error=f"{type(e).__name__}: {e}"))
        report.total += 1

    return report
