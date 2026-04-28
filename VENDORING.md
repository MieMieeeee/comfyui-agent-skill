# Vendored third-party code

## `comfy_api_simplified` (subset)

This skill ships a **minimal** copy of the `comfy_api_simplified` package from the
[run_comfyui_workflow](https://github.com/MieMieeeee/run_comfyui_workflow) project
so that `pip install -e .` does not need a `git+` dependency or network access to GitHub at install time.

**Included files** (under `scripts/comfy_api_simplified/`):

- `__init__.py` (reduced exports)
- `api.py`
- `workflow.py`
- `exceptions.py`

**Omitted** from upstream: `prompts/`, `scripts/`, examples, and other modules not used by this skill’s executor.

**Upstream commit** (from the local clone used when vendoring, for traceability; align with
`https://github.com/MieMieeeee/run_comfyui_workflow` when re-syncing):

`441d3ef48165d42c9165d5d3b399e7294fdddccc`

**License**: MIT. Full text in upstream repository; Copyright (c) 2024 deimos-deimos (as in upstream `LICENSE`).

**How to refresh from upstream**

1. Clone or update `https://github.com/MieMieeeee/run_comfyui_workflow`.
2. Copy the listed files over, adjust `__init__.py` if exports change.
3. Run `python -m pytest scripts/tests/ -q --ignore=scripts/tests/test_integration.py` and, if possible, a live ComfyUI smoke test.

**Environment override for config during tests**

`comfyui.config.local_config_path()` honors `COMFYUI_CONFIG_FILE` so tests and CI do not write the user’s
`config.local.json` in the skill root.

**Development install with `uv`**

From the skill root, `uv sync` (see `uv.lock` and `[tool.uv]` in `pyproject.toml`) installs the package and dev
dependencies; use `uv run pytest …` to run the test suite without activating the venv manually.
