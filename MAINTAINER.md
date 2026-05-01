# Maintainer Guide (ComfyUI Agent Skill)

This file is for maintainers who update workflows, mappings, or runtime behavior. Keep user-facing instructions in [SKILL.md](SKILL.md).

## Add or Update a Registered Workflow

Source of truth: [references/extension.md](references/extension.md)

## Import a Workflow (Generate Template)

Use the import command to copy a workflow JSON into `assets/workflows/` and generate a `*.config.template.json` for review:

```bash
uv run --no-sync python -m comfyui import-workflow /absolute/path/to/my-workflow.json
```

Optional:

- Override workflow id: `--id my_workflow_id`
- Overwrite existing imported files: `--force`

Short checklist:

1. Put the exported ComfyUI workflow JSON under `assets/workflows/`.
2. Generate a review template:

   ```bash
   uv run --no-sync python scripts/analyze_workflow.py assets/workflows/new_workflow.json
   ```

3. Review the generated `assets/workflows/new_workflow.config.template.json`.
4. Rename to `assets/workflows/new_workflow.config.json` only after review.
5. Preflight against the intended server:

   ```bash
   uv run --no-sync python -m comfyui generate --workflow new_workflow --preflight
   ```

## Run Tests

```bash
uv run --no-sync python -m pytest -q scripts/tests
```
